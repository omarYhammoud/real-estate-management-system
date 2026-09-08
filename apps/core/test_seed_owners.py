from io import StringIO

from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.properties.models import Owner


@override_settings(DEBUG=True)
class SeedOwnerLoginTests(TestCase):
    def seed(self, **options):
        call_command('seed_mock_data', stdout=StringIO(), **options)

    def test_existing_mock_owner_gets_login_and_rerun_preserves_password(self):
        owner = Owner.objects.create(full_name='Demo Owner 1', email='owner1@rms-demo.example')
        self.seed()
        owner.refresh_from_db()
        user = authenticate(username='demo_owner1', password='DemoOwner2026!')
        self.assertIsNotNone(user)
        self.assertEqual(owner.user_id, user.pk)
        self.assertEqual(user.role, 'owner')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(get_user_model().objects.count(), 4)
        user.set_password('ChangedDemoPassword!')
        user.save()
        self.seed()
        user.refresh_from_db()
        self.assertTrue(user.check_password('ChangedDemoPassword!'))
        self.assertEqual(get_user_model().objects.count(), 4)

    def test_dry_run_rolls_back_owner_links_and_users(self):
        owner = Owner.objects.create(full_name='Demo Owner 1', email='owner1@rms-demo.example')
        self.seed(dry_run=True)
        owner.refresh_from_db()
        self.assertIsNone(owner.user_id)
        self.assertFalse(get_user_model().objects.exists())
        self.assertEqual(Owner.objects.count(), 1)

    def test_username_collision_rolls_back_entire_seed(self):
        existing = get_user_model().objects.create_user(username='demo_owner2', password='ExistingPassword!')
        with self.assertRaises(CommandError):
            self.seed()
        self.assertFalse(Owner.objects.exists())
        self.assertEqual(get_user_model().objects.count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.role, 'tenant')

    def test_existing_linked_account_is_preserved(self):
        user = get_user_model().objects.create_user(username='custom_owner', password='ExistingPassword!', role='owner')
        owner = Owner.objects.create(full_name='Demo Owner 1', email='owner1@rms-demo.example', user=user)
        self.seed()
        owner.refresh_from_db()
        self.assertEqual(owner.user_id, user.pk)
        self.assertFalse(get_user_model().objects.filter(username='demo_owner1').exists())
