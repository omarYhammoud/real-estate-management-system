# Mock data

From the project root with your virtual environment active:

```console
python manage.py seed_mock_data --dry-run
python manage.py seed_mock_data
```

The first command validates the inserts and rolls them back. The second adds
4 owners, 4 properties, 24 units, 16 tenants, 16 contracts, 36 invoices,
32 payments with receipts, 12 deposits, 12 maintenance requests, 4 expenses,
and matching rent schedules and ledger records.

Includes occupied/vacant/maintenance units, active/expired contracts, and
paid/partially paid/unpaid overdue invoices. Uses fictional demo names and
reserved .example email addresses. No login accounts are created.

The command runs in one transaction, requires DEBUG=True, preserves existing
records, and uses stable references so rerunning does not duplicate records.
Dates are relative to the first run and retained on later runs.
