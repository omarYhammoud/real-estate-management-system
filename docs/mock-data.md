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
reserved .example email addresses. Four owner login accounts are created and
linked to the demo owners. Tenant login accounts are not created.

The command runs in one transaction, requires DEBUG=True, preserves existing
records, and uses stable references so rerunning does not duplicate records.
Dates are relative to the first run and retained on later runs.

## Owner login accounts

Run the seed command again to add logins to previously seeded owners:

```console
python manage.py seed_mock_data --dry-run
python manage.py seed_mock_data
```

New accounts use the development-only password `DemoOwner2026!`:

| Username | Linked owner | Property |
| --- | --- | --- |
| `demo_owner1` | Demo Owner 1 | [DEMO] Cedar Heights |
| `demo_owner2` | Demo Owner 2 | [DEMO] Harbor Offices |
| `demo_owner3` | Demo Owner 3 | [DEMO] Garden Court |
| `demo_owner4` | Demo Owner 4 | [DEMO] Maple Plaza |

Sign out of your current session, then use the normal application login form
with one of these usernames. These accounts have the `owner` role and are
active, but have no staff or superuser permissions. Each owner's `user` field
links to the corresponding account, allowing the existing owner dashboard
filters to select their properties.

Rerunning does not reset passwords or replace an owner's existing linked
account. If a demo username already exists while the owner is unlinked, the
command stops and rolls back all changes rather than taking over that account.
An administrator can review the existing user and link the correct Owner-role
account using the owner's User field in Django admin.

A dry run rolls back new users and owner links along with the other records;
the displayed demo credentials become usable only after a successful normal
run. Use these shared credentials only for local demonstration data.

## Verify the owner login changes

```console
python manage.py test apps.core.test_seed_owners
```

The tests cover authentication, linking already-seeded owners, rerun password
preservation, dry-run rollback, username conflicts, and existing linked accounts.

## Share with the team

Commit the command, tests, and this documentation on your feature branch and
open a pull request into `main`. After merging, each developer should pull the
changes and run `python manage.py seed_mock_data` in their own development
environment. Pulling code does not populate a local database.
