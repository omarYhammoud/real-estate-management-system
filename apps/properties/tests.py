from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Owner, Property, Unit, Tenant, RentalContract


User = get_user_model()


class UserProfileRelationshipTests(TestCase):
    def test_tenant_can_link_to_tenant_role_user(self):
        user = User.objects.create_user(username='linked-tenant', role=User.Role.TENANT)
        tenant = Tenant(user=user, full_name='Linked Tenant')
        tenant.full_clean()
        tenant.save()
        self.assertEqual(user.tenant_profile, tenant)

    def test_owner_can_link_to_owner_role_user(self):
        user = User.objects.create_user(username='linked-owner', role=User.Role.OWNER)
        owner = Owner(user=user, full_name='Linked Owner')
        owner.full_clean()
        owner.save()
        self.assertEqual(user.owner_profile, owner)

    def test_unlinked_profiles_remain_valid(self):
        tenant = Tenant(full_name='Unlinked Tenant')
        owner = Owner(full_name='Unlinked Owner')
        tenant.full_clean()
        owner.full_clean()

    def test_profile_role_mismatch_is_rejected(self):
        tenant_user = User.objects.create_user(username='wrong-owner', role=User.Role.TENANT)
        owner_user = User.objects.create_user(username='wrong-tenant', role=User.Role.OWNER)
        with self.assertRaises(ValidationError):
            Owner(user=tenant_user, full_name='Wrong Owner').full_clean()
        with self.assertRaises(ValidationError):
            Tenant(user=owner_user, full_name='Wrong Tenant').full_clean()


class PropertyRentalTests(TestCase):

    def setUp(self):

        self.owner = Owner.objects.create(
            full_name="Ahmad Khalil",
            phone="70123456",
            email="ahmad@example.com",
            address="Saida, Lebanon",
            status="active",
        )

        self.property = Property.objects.create(
            owner=self.owner,
            name="Saida Residence",
            address="Saida, Lebanon",
            property_type="residential",
            status="active",
        )

        self.unit = Unit.objects.create(
            property=self.property,
            unit_number="101",
            unit_type="Apartment",
            size_details="120 m²",
            rent_amount=500,
            status="vacant",
        )

        self.tenant = Tenant.objects.create(
            full_name="Mohammad Ali",
            phone="71123456",
            email="mohammad@example.com",
            identification_number="T001",
            status="active",
        )


    def test_valid_contract(self):

        contract = RentalContract(
            tenant=self.tenant,
            unit=self.unit,
            contract_reference="TEST-001",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 8, 31),
            monthly_rent=500,
            status="active",
        )

        contract.full_clean()
        contract.save()

        self.assertEqual(
            RentalContract.objects.count(),
            1
        )


    def test_end_date_before_start_date(self):

        contract = RentalContract(
            tenant=self.tenant,
            unit=self.unit,
            contract_reference="TEST-002",
            start_date=date(2026, 10, 10),
            end_date=date(2026, 10, 1),
            monthly_rent=500,
            status="active",
        )

        with self.assertRaises(ValidationError):

            contract.full_clean()


    def test_overlapping_active_contract_rejected(self):

        first_contract = RentalContract(
            tenant=self.tenant,
            unit=self.unit,
            contract_reference="TEST-003",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 8, 31),
            monthly_rent=500,
            status="active",
        )

        first_contract.full_clean()
        first_contract.save()


        second_tenant = Tenant.objects.create(
            full_name="Ali Hassan",
            phone="76123456",
            email="ali@example.com",
            identification_number="T002",
            status="active",
        )


        overlapping_contract = RentalContract(
            tenant=second_tenant,
            unit=self.unit,
            contract_reference="TEST-004",
            start_date=date(2026, 10, 1),
            end_date=date(2027, 2, 1),
            monthly_rent=500,
            status="active",
        )


        with self.assertRaises(ValidationError):

            overlapping_contract.full_clean()


    def test_non_overlapping_contract_allowed(self):

        first_contract = RentalContract(
            tenant=self.tenant,
            unit=self.unit,
            contract_reference="TEST-005",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 8, 31),
            monthly_rent=500,
            status="active",
        )

        first_contract.full_clean()
        first_contract.save()


        second_tenant = Tenant.objects.create(
            full_name="Ali Hassan",
            identification_number="T003",
            status="active",
        )


        second_contract = RentalContract(
            tenant=second_tenant,
            unit=self.unit,
            contract_reference="TEST-006",
            start_date=date(2027, 9, 1),
            end_date=date(2028, 8, 31),
            monthly_rent=500,
            status="active",
        )


        second_contract.full_clean()
        second_contract.save()


        self.assertEqual(
            RentalContract.objects.count(),
            2
        )


    def test_unit_with_active_contract_is_occupied(self):

        contract = RentalContract(
            tenant=self.tenant,
            unit=self.unit,
            contract_reference="TEST-007",
            start_date=date(2026, 1, 1),
            end_date=date(2027, 12, 31),
            monthly_rent=500,
            status="active",
        )

        contract.full_clean()
        contract.save()


        self.assertTrue(
            self.unit.is_currently_occupied
        )


    def test_unit_without_active_contract_is_available(self):

        self.assertFalse(
            self.unit.is_currently_occupied
        )


class PropertyManagementAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = Owner.objects.create(full_name='Authorization Owner')
        cls.property = Property.objects.create(
            owner=cls.owner,
            name='Authorization Property',
            address='Authorization Address',
            property_type=Property.PropertyType.RESIDENTIAL,
        )
        cls.unit = Unit.objects.create(
            property=cls.property,
            unit_number='AUTH-1',
            rent_amount=500,
        )
        cls.tenant = Tenant.objects.create(full_name='Authorization Tenant')
        cls.contract = RentalContract.objects.create(
            tenant=cls.tenant,
            unit=cls.unit,
            contract_reference='AUTH-CONTRACT-1',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_rent=500,
        )

    def endpoint_urls(self):
        return (
            reverse('properties:owner_list'),
            reverse('properties:owner_create'),
            reverse('properties:owner_update', args=[self.owner.pk]),
            reverse('properties:owner_delete', args=[self.owner.pk]),
            reverse('properties:property_list'),
            reverse('properties:property_create'),
            reverse('properties:property_update', args=[self.property.pk]),
            reverse('properties:property_delete', args=[self.property.pk]),
            reverse('properties:unit_list'),
            reverse('properties:unit_create'),
            reverse('properties:unit_update', args=[self.unit.pk]),
            reverse('properties:unit_delete', args=[self.unit.pk]),
            reverse('properties:tenant_list'),
            reverse('properties:tenant_detail', args=[self.tenant.pk]),
            reverse('properties:tenant_create'),
            reverse('properties:tenant_update', args=[self.tenant.pk]),
            reverse('properties:tenant_delete', args=[self.tenant.pk]),
            reverse('properties:contract_list'),
            reverse('properties:contract_detail', args=[self.contract.pk]),
            reverse('properties:contract_create'),
            reverse('properties:contract_update', args=[self.contract.pk]),
            reverse('properties:contract_delete', args=[self.contract.pk]),
        )

    def create_user(self, username, role, **kwargs):
        return User.objects.create_user(
            username=username,
            password='test-password',
            role=role,
            **kwargs,
        )

    def assert_all_endpoints(self, user, expected_status):
        self.client.force_login(user)
        for url in self.endpoint_urls():
            with self.subTest(user=user.username, url=url):
                self.assertEqual(self.client.get(url).status_code, expected_status)
        self.client.logout()

    def test_new_normal_user_defaults_to_tenant_role(self):
        user = User.objects.create_user(username='default-role-user')
        self.assertEqual(user.role, User.Role.TENANT)

    def test_anonymous_list_and_detail_requests_redirect_to_login(self):
        urls = (
            reverse('properties:owner_list'),
            reverse('properties:property_list'),
            reverse('properties:unit_list'),
            reverse('properties:tenant_list'),
            reverse('properties:tenant_detail', args=[self.tenant.pk]),
            reverse('properties:contract_list'),
            reverse('properties:contract_detail', args=[self.contract.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('accounts:login'), response.url)

    def test_anonymous_post_cannot_create_update_or_delete(self):
        original_name = self.property.name
        requests = (
            (reverse('properties:property_create'), {
                'owner': self.owner.pk, 'name': 'Unauthorized Property',
                'address': 'Unauthorized', 'property_type': Property.PropertyType.RESIDENTIAL,
            }),
            (reverse('properties:property_update', args=[self.property.pk]), {
                'owner': self.owner.pk, 'name': 'Unauthorized Update',
                'address': self.property.address, 'property_type': self.property.property_type,
            }),
            (reverse('properties:property_delete', args=[self.property.pk]), {}),
        )
        for url, data in requests:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, data).status_code, 302)
        self.property.refresh_from_db()
        self.assertEqual(self.property.name, original_name)
        self.assertFalse(Property.objects.filter(name='Unauthorized Property').exists())

    def test_admin_can_access_all_endpoints(self):
        self.assert_all_endpoints(
            self.create_user('properties-admin', User.Role.ADMIN), 200
        )

    def test_property_manager_can_access_all_endpoints(self):
        self.assert_all_endpoints(
            self.create_user('properties-manager', User.Role.PROPERTY_MANAGER), 200
        )

    def test_superuser_bypasses_role_restriction(self):
        self.assert_all_endpoints(
            self.create_user(
                'properties-superuser', User.Role.TENANT,
                is_staff=True, is_superuser=True,
            ),
            200,
        )

    def test_accountant_owner_and_tenant_receive_403_everywhere(self):
        for role in (User.Role.ACCOUNTANT, User.Role.OWNER, User.Role.TENANT):
            self.assert_all_endpoints(
                self.create_user(f'properties-{role}', role), 403
            )

    def test_forbidden_roles_cannot_mutate_property_data(self):
        original_name = self.property.name
        for role in (User.Role.ACCOUNTANT, User.Role.OWNER, User.Role.TENANT):
            user = self.create_user(f'mutation-{role}', role)
            self.client.force_login(user)
            create_response = self.client.post(reverse('properties:property_create'), {
                'owner': self.owner.pk, 'name': f'Forbidden {role}',
                'address': 'Forbidden', 'property_type': Property.PropertyType.RESIDENTIAL,
            })
            update_response = self.client.post(
                reverse('properties:property_update', args=[self.property.pk]),
                {
                    'owner': self.owner.pk, 'name': f'Changed by {role}',
                    'address': self.property.address,
                    'property_type': self.property.property_type,
                },
            )
            delete_response = self.client.post(
                reverse('properties:property_delete', args=[self.property.pk])
            )
            self.assertEqual(create_response.status_code, 403)
            self.assertEqual(update_response.status_code, 403)
            self.assertEqual(delete_response.status_code, 403)
            self.client.logout()

        self.property.refresh_from_db()
        self.assertEqual(self.property.name, original_name)
        self.assertFalse(Property.objects.filter(name__startswith='Forbidden').exists())

    def test_tenant_owner_and_accountant_cannot_view_global_management(self):
        global_urls = (
            reverse('properties:property_list'),
            reverse('properties:tenant_list'),
            reverse('properties:contract_list'),
        )
        for role in (User.Role.TENANT, User.Role.OWNER, User.Role.ACCOUNTANT):
            user = self.create_user(f'global-{role}', role)
            self.client.force_login(user)
            for url in global_urls:
                with self.subTest(role=role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
            self.client.logout()
