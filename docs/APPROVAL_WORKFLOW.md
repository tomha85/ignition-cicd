# Approve after Validate — GitHub → EAM TEST Controller

## Intended behavior

```text
Run workflow / push Factory A source
               |
               v
         VALIDATE (automatic)
               |
        PASS / FAIL
               |
         PASS only
               v
   WAITING FOR YOUR GITHUB REVIEW
      Environment: ignition-test
      Required reviewer: tomha85
          /              \
    REJECT              APPROVE AND DEPLOY
       |                      |
     STOP                 Backup first
                               |
                        Stage selected native project
                        on EAM TEST Controller
                               |
                        Verify source SHA256
                        + Controller project scan
                               |
                        Upload evidence
```

## Exactly two GitHub jobs

The first job `Validate` runs automatically.
The standard manual workflow runs from `main` with exactly two inputs:
Factory and Project. The Factory and Project text fields are validated from factory.json;
validation confirms that the selected project actually belongs to the factory.
The second `Stage` declares `needs: validate` and
`environment: ignition-test`.

GitHub's native Required reviewer protection makes **Stage WAIT** until
`tomha85` chooses **Review deployments → Approve and deploy**. The workflow
has no reviewer-readiness job and no approval polling loop. The internal
current-run approval check runs only *after* GitHub releases the Stage job.
It does not create a separate block.

The environment must keep Required reviewer `tomha85` enabled. Native
Waiting depends on that GitHub setting, not on a YAML step.

## One-time setup in GitHub UI — REQUIRED

1. Go to your repository:
   `https://github.com/tomha85/ignition-cicd/settings/environments`.
2. Select the existing environment **`ignition-test`** (keep the existing
   environment secrets/settings used by the TEST staging job).
3. Under **Deployment protection rules**, enable **Required reviewers**.
4. Add GitHub user **`tomha85`** as the required reviewer. Save protection rules.
5. **Leave Prevent self-review unchecked** if you will start and approve the same
   workflow yourself. If you enable Prevent self-review, another reviewer must
   approve instead; the current smoke approval gate only allows `tomha85`.
6. For extra control, disable **Allow administrators to bypass configured
   protection rules**, if that control is available.
7. Do **not** edit `main`, Agent task configuration, or production settings.

GitHub's availability of required reviewers depends on repository visibility
and GitHub plan. If GitHub does not expose the Required reviewers setting,
**do not** weaken or delete the code gate to deploy: it will stay HOLD.

## Running the two-field standard workflow

1. Go to Actions → **Ignition EAM - Select Factory & Project (TEST)**.
2. Choose branch **main**, Factory **lab-warehouse**, Project **WarehouseHMI**
   (or **FactoryASmoke**).
3. Click **Run workflow**; Gateway `warehouse-main` is resolved from
   `factories/lab-warehouse/factory.json`, not requested from you.
4. Validate must PASS, then Stage shows **Waiting**.
5. Click **Review deployments → ignition-test → Approve and deploy**.
6. Stage automatically backs up and verifies the TEST Controller.
7. Review deployment evidence and project description in the Controller.

Other factories can be source-validated but cannot stage until each
TEST Controller target is separately commissioned. Ambiguous project-to-
Gateway associations fail validation. The user manages Agent tasks later.

## Security properties

- Approved identity: `tomha85`, verified using GitHub REST
  `GET /repos/{owner}/{repo}/actions/runs/{run_id}/approvals`.
- The approval **must be for the current run** and the **`ignition-test`**
  environment. Wrong reviewer, rejected review, missing API access or no
  approval produces **HOLD**.
- Only the first attempt of a run is eligible. For a failed run, launch a
  **fresh workflow run** rather than reusing old review history.
- Any project registered under a commissioned and explicitly approved
  isolated TEST Gateway may stage after review. The current registered
  TEST Gateway is `lab-warehouse/warehouse-main` (both native projects).
- Other factories stay validate-only until real independent TEST commissioning.
- Factory B/C remain source validation/build only, regardless of approval.
- Before mutation, staging takes TEST Controller and Agent **project directory
  archives**. These are not independently qualified full-Gateway backups.
- On any deployment error, the Controller project update adapter attempts
  rollback and writes a HOLD/rollback report.
- **No EAM Agent task is created or run**. You will manage Agent tasks later.
- The stage job runs only on the isolated local `ignition-lab` runner.
- Production is not authorized.

## Troubleshooting

**Validation FAIL:** No approval is requested because staging depends on
successful validation.

**Validate PASS but Stage does not wait:** Check `ignition-test` Required reviewers are still configured for `tomha85` and start a new run.

**Stage unexpectedly starts and fails with HOLD_NO_APPROVAL:** A GitHub
environment rule may have been changed between readiness and staging, the
environment was bypassed, or the approval API was inaccessible. The extra
defense-in-depth guard intentionally refuses Controller writes.

**GitHub API 403/404:** The stage job requires `actions: read` for
`GITHUB_TOKEN`. Do not substitute an unscoped Personal Access Token.

**No Review deployments button:** Check environment protection rules and
your GitHub account permissions. Code changes cannot create a required reviewer
by themselves.

**Agent task:** It is intentionally out of this workflow. Stage Controller
success does not prove Agent or Perspective runtime success.
