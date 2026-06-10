## Add Early Warning Tests and Dashboard Status Alerts

Companion HTML reference for this plan:

- `/home/adamsl/letta-code/dashboard/tests_and_status_alerts/tests_and_status_alerts.html`

We need a way to catch this type of problem earlier.

Do **not** apply the actual production fix yet.

First, create failing tests that detect this problem before it reaches users.

## Unit Tests

Create unit tests that catch this type of error in the future.

The unit tests should:

1. Reproduce the current failure.
2. Fail before the fix is applied.
3. Cover the main expected behavior.
4. Cover important edge cases.
5. Verify that the system correctly identifies the problem condition.
6. Verify that healthy systems are not incorrectly marked as broken.

Run the unit tests after creating them so we can confirm they fail for the right reason.

## Integration Tests

After the unit tests are written, create failing integration tests that verify the dashboard warning behavior.

The integration tests should confirm that:

1. When this type of problem happens, the main **Status** tab/button flashes **yellow and white** as an early warning.
2. When the user clicks the **Status** tab/button, the specific related status section also flashes **yellow and white**.
3. Healthy status sections display **green**.
4. Remove the current blue status color from these Status tabs.
5. Warning-level problems use **yellow and white blinking**.
6. Critical problems use **red and white blinking**.

Example:

If the **Server** status is critically unhealthy, the Server status section should blink **red and white**.

If the system detects an early warning but not a critical failure, the affected status section should blink **yellow and white**.

If a status section is healthy, it should be **green**.

## Expected Workflow

1. Write the unit tests first.
2. Run the unit tests and confirm they fail.
3. Write the integration tests.
4. Run the integration tests and confirm they fail.
5. Do not apply the actual fix yet.
6. After we review the failing tests, we will decide on the implementation fix.
