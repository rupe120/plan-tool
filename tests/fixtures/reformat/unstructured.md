# Idle session timeout

We need to log users out after a stretch of inactivity. Right now a
signed-in session never expires on its own — once the JWT lands in
local storage it stays usable until the user explicitly signs out or
the token's hard expiry kicks in days later. That's fine for the
happy path on a personal device, but the shared-kiosk case where a
student walks away from a school laptop leaves the next person with
an authenticated session.

The fix has two parts: a client-side idle watcher that listens for
pointer/keyboard activity and triggers a sign-out after 30 minutes
of silence, and a small backend change so the AppSync session log
records the timeout reason distinctly from a manual sign-out (we
care about the analytics split). The watcher lives in the shared
package because both web and mobile need it; the backend change is
a single Lambda + a new SessionLog reason enum value.

We'd like the timeout duration to be a setting an admin can tweak
without a deploy — store it under `APP_CONFIG / IDLE_TIMEOUT_MS` in
the existing Settings table and read it through the app-mode Lambda
Function URL. Default 30 minutes if the setting is absent.

Acceptance: signed-in user with no input for the configured idle
duration is signed out automatically; the SessionLog row for that
signout carries reason `IDLE_TIMEOUT`; admin can change the
threshold via the app-settings admin UI and the change takes effect
on the next idle window without a reload.
