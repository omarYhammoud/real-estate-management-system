from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Owner, Property, Unit, Tenant, RentalContract


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