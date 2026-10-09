#!/bin/bash
# Paste into Google Cloud Shell. Fill the four values, then run.
# Part 1 creates only LAB_PROJECT_ID. Part 2 only reads NAVERA_PROJECT_ID.
# No billing-account IAM role. No billing unlink. No second project is modified.
set -euo pipefail

LAB_PROJECT_ID="vantio-lab-oct08"
NAVERA_PROJECT_ID="REPLACE_NAVERA_PROJECT_ID"
BILLING_ACCOUNT_ID="REPLACE_BILLING_ACCOUNT_ID"
CREDIT_USD="REPLACE_CREDIT_USD"
LAB_BUDGET_USD="5"

ATTR_COND="assertion.repository=='vantioai/vantio-open-core' && assertion.ref=='refs/heads/main' && (assertion.job_workflow_ref=='vantioai/vantio-open-core/.github/workflows/gcp-lab-cost-gate.yml@refs/heads/main' || assertion.job_workflow_ref=='vantioai/vantio-open-core/.github/workflows/gcp-lab-provision.yml@refs/heads/main' || assertion.job_workflow_ref=='vantioai/vantio-open-core/.github/workflows/gcp-lab-collect.yml@refs/heads/main' || assertion.job_workflow_ref=='vantioai/vantio-open-core/.github/workflows/gcp-lab-teardown.yml@refs/heads/main' || assertion.job_workflow_ref=='vantioai/vantio-open-core/.github/workflows/gcp-lab-sweeper.yml@refs/heads/main' || assertion.job_workflow_ref=='vantioai/vantio-open-core/.github/workflows/gcp-lab-verify-removed.yml@refs/heads/main')"

need_project() {
  local want="$1"
  gcloud config set project "$want" >/dev/null
  local active
  active="$(gcloud config get-value project 2>/dev/null || true)"
  if [[ "$active" != "$want" ]]; then
    echo "STOP: active project is [${active}], expected [${want}]" >&2
    exit 1
  fi
}

[[ "$LAB_PROJECT_ID" =~ ^vantio-lab-[a-z][a-z0-9-]{2,18}$ ]] || { echo "STOP: LAB_PROJECT_ID must look like vantio-lab-oct08" >&2; exit 1; }
[[ "$LAB_PROJECT_ID" != *navera* && "$NAVERA_PROJECT_ID" != "$LAB_PROJECT_ID" && "$NAVERA_PROJECT_ID" != vantio-lab-* ]] || { echo "STOP: lab and Navera project ids are mixed" >&2; exit 1; }
[[ "$NAVERA_PROJECT_ID" != REPLACE_* && -n "$NAVERA_PROJECT_ID" ]] || { echo "STOP: set NAVERA_PROJECT_ID" >&2; exit 1; }
[[ "$BILLING_ACCOUNT_ID" =~ ^[A-Za-z0-9]{6}-[A-Za-z0-9]{6}-[A-Za-z0-9]{6}$ ]] || { echo "STOP: set BILLING_ACCOUNT_ID like 012345-6789AB-CDEF01" >&2; exit 1; }
[[ "$CREDIT_USD" != REPLACE_* ]] || { echo "STOP: set CREDIT_USD from the billing page" >&2; exit 1; }
read -r CREDIT_CENTS BUDGET_CENTS < <(python3 -c 'import sys; c=float(sys.argv[1]); b=float(sys.argv[2]); assert c>b>1; print(int(round(c*100)), int(round(b*100)))' "$CREDIT_USD" "$LAB_BUDGET_USD")

echo "PART 1 lab ${LAB_PROJECT_ID}"
need_project "$LAB_PROJECT_ID"
if ! gcloud projects describe "$LAB_PROJECT_ID" >/dev/null 2>&1; then
  need_project "$LAB_PROJECT_ID"
  gcloud projects create "$LAB_PROJECT_ID" --name="Vantio lab"
fi
need_project "$LAB_PROJECT_ID"
if gcloud projects get-iam-policy "$LAB_PROJECT_ID" --format=json | grep -qi 'navera.io'; then
  echo "STOP: ${LAB_PROJECT_ID} already has a navera.io member" >&2
  exit 1
fi
gcloud billing projects link "$LAB_PROJECT_ID" --billing-account="$BILLING_ACCOUNT_ID"
gcloud projects update "$LAB_PROJECT_ID" --update-labels="vantio-credit-cents=${CREDIT_CENTS},vantio-budget-cents=${BUDGET_CENTS},vantio-cap=alerts-only"
gcloud services enable compute.googleapis.com iam.googleapis.com iamcredentials.googleapis.com cloudresourcemanager.googleapis.com sts.googleapis.com cloudbilling.googleapis.com billingbudgets.googleapis.com orgpolicy.googleapis.com --project="$LAB_PROJECT_ID"
gcloud resource-manager org-policies enable-enforce iam.disableServiceAccountKeyCreation --project="$LAB_PROJECT_ID" || echo "org policy not applied; no key will be created"
if ! gcloud billing budgets list --billing-account="$BILLING_ACCOUNT_ID" --format='value(displayName)' | grep -qx 'Vantio lab cap'; then
  need_project "$LAB_PROJECT_ID"
  gcloud billing budgets create --billing-account="$BILLING_ACCOUNT_ID" --display-name="Vantio lab cap" --budget-amount="${LAB_BUDGET_USD}USD" --filter-projects="projects/${LAB_PROJECT_ID}" --threshold-rule=percent=0.50 --threshold-rule=percent=0.90 --threshold-rule=percent=1.0
fi
SA="vantio-lab-gha@${LAB_PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts describe "$SA" --project="$LAB_PROJECT_ID" >/dev/null 2>&1 || gcloud iam service-accounts create vantio-lab-gha --project="$LAB_PROJECT_ID" --display-name="GitHub Actions lab"
ROLE_FILE="$(mktemp)"
cat > "$ROLE_FILE" << 'EOF'
title: Vantio lab runner
description: One e2-micro in the lab project. No keys and no IAM edits.
stage: GA
includedPermissions:
- compute.instances.create
- compute.instances.delete
- compute.instances.get
- compute.instances.list
- compute.instances.setLabels
- compute.instances.setMetadata
- compute.instances.getSerialPortOutput
- compute.disks.create
- compute.disks.delete
- compute.disks.get
- compute.disks.list
- compute.zoneOperations.get
- compute.globalOperations.get
- compute.machineTypes.get
- compute.networks.get
- compute.subnetworks.get
- compute.subnetworks.use
- compute.projects.get
- resourcemanager.projects.get
- resourcemanager.projects.getIamPolicy
- serviceusage.services.get
- serviceusage.services.list
EOF
gcloud iam roles describe vantioLabRunner --project="$LAB_PROJECT_ID" >/dev/null 2>&1 || gcloud iam roles create vantioLabRunner --project="$LAB_PROJECT_ID" --file="$ROLE_FILE"
rm -f "$ROLE_FILE"
need_project "$LAB_PROJECT_ID"
gcloud projects add-iam-policy-binding "$LAB_PROJECT_ID" --member="serviceAccount:${SA}" --role="projects/${LAB_PROJECT_ID}/roles/vantioLabRunner" >/dev/null
gcloud iam workload-identity-pools describe github-actions --project="$LAB_PROJECT_ID" --location=global >/dev/null 2>&1 || gcloud iam workload-identity-pools create github-actions --project="$LAB_PROJECT_ID" --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers describe github --project="$LAB_PROJECT_ID" --location=global --workload-identity-pool=github-actions >/dev/null 2>&1 || gcloud iam workload-identity-pools providers create-oidc github --project="$LAB_PROJECT_ID" --location=global --workload-identity-pool=github-actions --display-name="GitHub OIDC" --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.workflow_ref=assertion.job_workflow_ref" --attribute-condition="$ATTR_COND"
NUM="$(gcloud projects describe "$LAB_PROJECT_ID" --format='value(projectNumber)')"
gcloud iam service-accounts add-iam-policy-binding "$SA" --project="$LAB_PROJECT_ID" --role="roles/iam.workloadIdentityUser" --member="principal://iam.googleapis.com/projects/${NUM}/locations/global/workloadIdentityPools/github-actions/subject/repo:vantioai/vantio-open-core:ref:refs/heads/main" >/dev/null
need_project "$LAB_PROJECT_ID"
gcloud projects describe "$LAB_PROJECT_ID" --format='value(labels.vantio-cap)' | grep -qx alerts-only
gcloud billing projects describe "$LAB_PROJECT_ID" --format='value(billingEnabled)' | grep -qx True
gcloud projects get-iam-policy "$LAB_PROJECT_ID" --format=json | grep -qi 'navera.io' && { echo "STOP: navera.io appeared on the lab project" >&2; exit 1; }
if gcloud billing accounts get-iam-policy "$BILLING_ACCOUNT_ID" --format=json | grep -q "$SA"; then
  echo "STOP: lab service account is on the billing account" >&2
  exit 1
fi
echo "LAB_OK"
echo "GCP_LAB_PROJECT=${LAB_PROJECT_ID}"
echo "GCP_LAB_WIF_PROVIDER=projects/${NUM}/locations/global/workloadIdentityPools/github-actions/providers/github"
echo "GCP_LAB_SERVICE_ACCOUNT=${SA}"

echo "PART 2 read ${NAVERA_PROJECT_ID}"
need_project "$NAVERA_PROJECT_ID"
OUT="${HOME}/navera-access-readonly"
mkdir -p "$OUT"
gcloud projects describe "$NAVERA_PROJECT_ID" --format=json > "$OUT/project.json"
gcloud billing projects describe "$NAVERA_PROJECT_ID" --format=json > "$OUT/billing.json"
gcloud projects get-iam-policy "$NAVERA_PROJECT_ID" --format=json > "$OUT/iam.json"
gcloud services list --enabled --project="$NAVERA_PROJECT_ID" --format=json > "$OUT/services.json" || printf '[]\n' > "$OUT/services.json"
gcloud iam service-accounts list --project="$NAVERA_PROJECT_ID" --format=json > "$OUT/service-accounts.json" || printf '[]\n' > "$OUT/service-accounts.json"
python3 - "$NAVERA_PROJECT_ID" "$OUT" << 'PY'
import json, subprocess, sys
from pathlib import Path
pid, out = sys.argv[1], Path(sys.argv[2])
sas = json.loads((out / "service-accounts.json").read_text() or "[]")
keys = []
for sa in sas:
    email = sa.get("email")
    if not email:
        continue
    listed = subprocess.run(["gcloud", "iam", "service-accounts", "keys", "list", f"--iam-account={email}", "--managed-by=user", "--format=json"], capture_output=True, text=True)
    for key in json.loads(listed.stdout or "[]"):
        keys.append({"email": email, "name": key.get("name"), "keyType": key.get("keyType"), "validAfterTime": key.get("validAfterTime")})
(out / "user-managed-keys.json").write_text(json.dumps(keys, indent=2) + "\n")
iam = json.loads((out / "iam.json").read_text())
billing = json.loads((out / "billing.json").read_text())
lines = [f"# Inventory {pid}", "", f"Billing enabled: {billing.get('billingEnabled')}. Account: {billing.get('billingAccountName')}.", "", "| Member | Role |", "| --- | --- |"]
for binding in iam.get("bindings") or []:
    for member in binding.get("members") or []:
        lines.append(f"| `{member}` | `{binding.get('role')}` |")
lines += ["", "## User-managed keys", ""]
if not keys:
    lines.append("None.")
for key in keys:
    lines.append(f"- {key['email']} name={key['name']} type={key['keyType']} created={key['validAfterTime']}")
(out / "inventory.md").write_text("\n".join(lines) + "\n")
PY
for region in us-central1 us-east1 us-east4; do
  gcloud builds connections list --project="$NAVERA_PROJECT_ID" --region="$region" --format=json > "$OUT/builds-${region}.json" || printf '[]\n' > "$OUT/builds-${region}.json"
  gcloud developer-connect connections list --project="$NAVERA_PROJECT_ID" --location="$region" --format=json > "$OUT/devcon-${region}.json" || printf '[]\n' > "$OUT/devcon-${region}.json"
done
gcloud compute instances list --project="$NAVERA_PROJECT_ID" --format=json > "$OUT/instances.json" || printf '[]\n' > "$OUT/instances.json"
need_project "$NAVERA_PROJECT_ID"
echo "INVENTORY ${OUT}/inventory.md"
cat "$OUT/inventory.md"
