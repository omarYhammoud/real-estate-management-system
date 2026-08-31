# Real Estate Management System

Django full-stack project — Group 8: **Omar • Waad • Alyousof • Chaheen**

A rental-financial workflow: `Property → Tenant → Rental Contract → Rent Schedule → Invoice → Payment → Receipt → Dashboard / Reports`.
Full context in `docs/` (BRD, ERD, wireframes).

---

## 1. Project structure

```
real_estate_management_system/
├── config/                     # project settings & root URLs (shared — see §5)
│   └── settings/
│       ├── base.py             # shared settings
│       ├── dev.py               # local dev (SQLite, DEBUG=True)
│       └── prod.py              # production (Postgres, security headers)
├── apps/
│   ├── core/                   # shared: TimeStampedModel, RoleRequiredMixin, template tags
│   ├── accounts/                # Chaheen — User, auth, roles
│   ├── properties/               # Omar — Owner, Property, Unit, Tenant, RentalContract
│   ├── billing/                  # Waad — RentSchedule, Invoice, InvoiceLineItem, Payment, Receipt
│   ├── operations/               # Alyousof — SecurityDeposit, DepositDeduction, DepositRefund, MaintenanceRequest, Expense
│   └── finance/                  # Chaheen — FinancialTransaction, Dashboard, Reports
├── templates/                  # shared base.html, navbar, sidebar, footer
├── static/                     # shared css/js/img
├── media/                      # user-uploaded files (gitignored, folder kept)
├── docs/                       # BRD, ERD, wireframes
├── requirements/                # base.txt / dev.txt / prod.txt
├── .env.example                 # copy to .env
├── docker-compose.yml           # optional (Postgres-backed local run)
└── manage.py
```

Each app has the standard Django layout: `models.py`, `views.py`, `urls.py`, `forms.py`, `admin.py`, `tests.py`, `migrations/`, and its own `templates/<app_name>/` folder. **You should only need to touch your own app folder** plus the one line in `config/urls.py` that includes it (already there).

---

## 2. Who owns what

| Member | App | Models |
|---|---|---|
| **Omar** | `apps/properties` | Owner, Property, Unit, Tenant, RentalContract |
| **Waad** | `apps/billing` | RentSchedule, Invoice, InvoiceLineItem, Payment, Receipt |
| **Alyousof** | `apps/operations` | SecurityDeposit, DepositDeduction, DepositRefund, MaintenanceRequest, Expense |
| **Chaheen** | `apps/accounts` + `apps/finance` | User/roles + FinancialTransaction, Dashboard, Reports |
| **Everyone** | `apps/core`, `templates/`, `static/` | Shared base model, mixins, base template — coordinate before editing |

Model skeletons already match the ERD (fields, FKs, choices) so you can start writing views/forms/templates and migrate right away. Cross-app foreign keys are wired for you — e.g. `apps/billing/models.py` imports `RentalContract`/`Tenant` from `apps.properties`, `apps/operations` and `apps/finance` reference the user via `settings.AUTH_USER_MODEL`.

---

## 3. Getting started (each team member)

```bash
git clone <repo-url>
cd real_estate_management_system

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements/dev.txt

cp .env.example .env             # then set DJANGO_SECRET_KEY to any random string

python manage.py migrate
python manage.py createsuperuser

python manage.py runserver
```

Open `http://127.0.0.1:8000/`. `manage.py` defaults to `config.settings.dev`, so this works with zero configuration — SQLite database file `db.sqlite3` is created automatically and gitignored.

To use Postgres locally instead: `docker compose up`.

---

## 4. Git workflow

- Never commit directly to `main`.
- Work on your own feature branch:
  ```
  feature/omar-property-rental
  feature/waad-billing-payments
  feature/alyousof-deposits-operations
  feature/chaheen-auth-reports
  ```
- Open a pull request into `main` when a task is ready; at least one other member reviews before merging.
- Pull `main` and re-run `python manage.py migrate` after every merge that touches models.
- **Migrations conflict easily** across branches — if you and another member both change models, rebase and regenerate migrations (`python manage.py makemigrations <your_app>`) rather than hand-editing someone else's migration file.

---

## 5. Shared conventions (agree on these before diverging)

- **Model/field naming:** snake_case fields, PascalCase model names — already followed in the model skeletons.
- **URL naming:** each app is namespaced (`properties:`, `billing:`, `operations:`, `finance:`, `accounts:`); URL patterns are plural nouns, e.g. `/billing/invoices/`, `/billing/invoices/<id>/`.
- **Templates:** extend `templates/base.html`; put app-specific templates under `apps/<app>/templates/<app>/`, not the project-level `templates/` folder.
- **Roles:** `admin`, `property_manager`, `accountant`, `owner`, `tenant` (see `apps/accounts/models.py`). Gate financial views with `apps.core.mixins.RoleRequiredMixin`.
- **Testing:** put tests in each app's `tests.py`; CI (`.github/workflows/ci.yml`) runs `manage.py test` on every PR.
- Anyone changing something genuinely shared (`apps/core`, `templates/base.html`, `static/css/base.css`, `config/settings/*`) should flag it to the team first — these are the files most likely to cause merge conflicts.

---

## 6. Documentation

- `docs/BRD/` — Business Requirements Document
- `docs/ERD/` — Entity-Relationship Diagram
- `docs/wireframes/` — UI wireframes

---

## 7. Environments

| | `dev` (default) | `prod` |
|---|---|---|
| Settings module | `config.settings.dev` | `config.settings.prod` |
| Database | SQLite (auto-created) | Postgres (env vars) |
| DEBUG | True | False |
| Use for | day-to-day development | deployment / demo server |
