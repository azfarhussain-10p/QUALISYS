/**
 * Notification Preferences Page
 * Story: 1-8-profile-notification-preferences
 * AC6 — email category toggles, frequency dropdown, digest time/day picker
 * AC7 — security_alerts non-disableable
 */

import { useState, useEffect } from 'react'
import { Loader2, Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { userApi, NotificationPreferences, ApiError } from '@/lib/api'

// ---------------------------------------------------------------------------
// Toggle row
// ---------------------------------------------------------------------------
function ToggleRow({
  id,
  label,
  description,
  checked,
  disabled,
  disabledReason,
  onChange,
}: {
  id: string
  label: string
  description?: string
  checked: boolean
  disabled?: boolean
  disabledReason?: string
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-border last:border-0">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <Label htmlFor={id} className="text-sm font-medium cursor-pointer">
            {label}
          </Label>
          {disabled && disabledReason && (
            <span
              title={disabledReason}
              className="inline-flex items-center text-muted-foreground"
              aria-label={disabledReason}
            >
              <Lock className="h-3 w-3" />
            </span>
          )}
        </div>
        {description && (
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        )}
        {disabled && disabledReason && (
          <p className="text-xs text-muted-foreground mt-0.5 italic">{disabledReason}</p>
        )}
      </div>
      {/* Custom toggle */}
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
          checked ? 'bg-primary' : 'bg-input'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        data-testid={`toggle-${id}`}
      >
        <span
          className={`pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform ${
            checked ? 'translate-x-4' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// NotificationsPage
// ---------------------------------------------------------------------------
export default function NotificationsPage() {
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Local form state (mirrors prefs)
  const [testCompletions, setTestCompletions] = useState(true)
  const [testFailures, setTestFailures] = useState(true)
  const [teamChanges, setTeamChanges] = useState(true)
  const [frequency, setFrequency] = useState<'realtime' | 'daily' | 'weekly'>('realtime')
  const [digestTime, setDigestTime] = useState('09:00')
  const [digestDay, setDigestDay] = useState('monday')

  useEffect(() => {
    userApi
      .getNotifications()
      .then((data) => {
        setPrefs(data)
        setTestCompletions(data.email_test_completions)
        setTestFailures(data.email_test_failures)
        setTeamChanges(data.email_team_changes)
        setFrequency(data.email_frequency)
        setDigestTime(data.digest_time)
        setDigestDay(data.digest_day)
      })
      .catch((err) => {
        setFetchError(err instanceof ApiError ? err.message : 'Failed to load preferences.')
      })
      .finally(() => setLoading(false))
  }, [])

  const isDirty =
    prefs &&
    (testCompletions !== prefs.email_test_completions ||
      testFailures !== prefs.email_test_failures ||
      teamChanges !== prefs.email_team_changes ||
      frequency !== prefs.email_frequency ||
      digestTime !== prefs.digest_time ||
      digestDay !== prefs.digest_day)

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const updated = await userApi.updateNotifications({
        email_test_completions: testCompletions,
        email_test_failures: testFailures,
        email_team_changes: teamChanges,
        email_security_alerts: true, // AC7: always true
        email_frequency: frequency,
        digest_time: digestTime,
        digest_day: digestDay,
      })
      setPrefs(updated)
      setTestCompletions(updated.email_test_completions)
      setTestFailures(updated.email_test_failures)
      setTeamChanges(updated.email_team_changes)
      setFrequency(updated.email_frequency)
      setDigestTime(updated.digest_time)
      setDigestDay(updated.digest_day)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Failed to save preferences.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12" data-testid="notifications-loading">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (fetchError) {
    return (
      <div
        role="alert"
        className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
        data-testid="notifications-fetch-error"
      >
        {fetchError}
      </div>
    )
  }

  return (
    <div className="space-y-8 max-w-lg" data-testid="notifications-page">
      {/* Email notifications — AC6 */}
      <section>
        <h3 className="text-base font-medium mb-1">Email Notifications</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Choose which events trigger an email notification.
        </p>

        <div className="rounded-md border border-border px-4">
          <ToggleRow
            id="email-test-completions"
            label="Test run completions"
            description="Notified when a test run finishes successfully."
            checked={testCompletions}
            onChange={setTestCompletions}
          />
          <ToggleRow
            id="email-test-failures"
            label="Test failures"
            description="Notified when a test run encounters failures."
            checked={testFailures}
            onChange={setTestFailures}
          />
          <ToggleRow
            id="email-team-changes"
            label="Team member changes"
            description="Notified when members are added or removed from your team."
            checked={teamChanges}
            onChange={setTeamChanges}
          />
          {/* AC6, AC7: security alerts non-disableable */}
          <ToggleRow
            id="email-security-alerts"
            label="Security alerts"
            description="Login from a new device, password changes, and 2FA events."
            checked={true}
            disabled={true}
            disabledReason="Security notifications cannot be disabled."
            onChange={() => {}}
          />
        </div>
      </section>

      {/* Email frequency — AC6 */}
      <section>
        <h3 className="text-base font-medium mb-1">Email Frequency</h3>
        <p className="text-sm text-muted-foreground mb-3">
          How often you'd like to receive email notifications.
        </p>

        <div className="space-y-2">
          {(['realtime', 'daily', 'weekly'] as const).map((freq) => (
            <label
              key={freq}
              className="flex items-center gap-3 cursor-pointer rounded-md border border-border px-4 py-3 hover:bg-secondary/30 transition-colors"
              data-testid={`frequency-option-${freq}`}
            >
              <input
                type="radio"
                name="email-frequency"
                value={freq}
                checked={frequency === freq}
                onChange={() => setFrequency(freq)}
                className="h-4 w-4 accent-primary"
              />
              <div>
                <span className="text-sm font-medium capitalize">
                  {freq === 'realtime' ? 'Real-time' : freq === 'daily' ? 'Daily digest' : 'Weekly digest'}
                </span>
                <p className="text-xs text-muted-foreground">
                  {freq === 'realtime' && 'Emails sent as events happen.'}
                  {freq === 'daily' && 'One digest email per day at your chosen time.'}
                  {freq === 'weekly' && 'One digest email per week on your chosen day.'}
                </p>
              </div>
            </label>
          ))}
        </div>

        {/* Digest time — shown for daily + weekly */}
        {(frequency === 'daily' || frequency === 'weekly') && (
          <div className="mt-4 flex flex-wrap gap-4">
            {frequency === 'weekly' && (
              <div>
                <Label htmlFor="digest-day" className="text-sm">
                  Day of week
                </Label>
                <select
                  id="digest-day"
                  value={digestDay}
                  onChange={(e) => setDigestDay(e.target.value)}
                  className="mt-1 block rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  data-testid="digest-day-select"
                >
                  {['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map(
                    (day) => (
                      <option key={day} value={day}>
                        {day.charAt(0).toUpperCase() + day.slice(1)}
                      </option>
                    ),
                  )}
                </select>
              </div>
            )}

            <div>
              <Label htmlFor="digest-time" className="text-sm">
                Time
              </Label>
              <input
                id="digest-time"
                type="time"
                value={digestTime}
                onChange={(e) => setDigestTime(e.target.value)}
                className="mt-1 block rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                data-testid="digest-time-input"
              />
              <p className="mt-1 text-xs text-muted-foreground">In your profile timezone.</p>
            </div>
          </div>
        )}
      </section>

      {/* Save — AC7 */}
      <section>
        {saveError && (
          <div
            role="alert"
            className="mb-3 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive"
            data-testid="save-error"
          >
            {saveError}
          </div>
        )}
        {saveSuccess && (
          <div
            className="mb-3 rounded-md bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-700"
            data-testid="save-success"
          >
            Preferences saved.
          </div>
        )}
        <Button
          onClick={handleSave}
          disabled={!isDirty || saving}
          data-testid="save-notifications-btn"
        >
          {saving ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving…</>
          ) : (
            'Save Preferences'
          )}
        </Button>
      </section>
    </div>
  )
}
