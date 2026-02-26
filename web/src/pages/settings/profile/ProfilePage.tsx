/**
 * Profile Settings Page
 * Story: 1-8-profile-notification-preferences
 * AC1 — tabbed settings layout (Profile, Security, Notifications)
 * AC2 — edit full name
 * AC3 — avatar upload/remove (presigned S3), initials fallback
 * AC4 — timezone searchable dropdown (IANA)
 */

import { useState, useEffect, useRef } from 'react'
import { Loader2, Upload, X, Camera } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  userApi,
  UserProfileResponse,
  ApiError,
} from '@/lib/api'

// ---------------------------------------------------------------------------
// Common timezones list (IANA) — covers most users without needing a full library
// ---------------------------------------------------------------------------
const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Anchorage',
  'America/Honolulu',
  'America/Toronto',
  'America/Vancouver',
  'America/Sao_Paulo',
  'America/Argentina/Buenos_Aires',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Amsterdam',
  'Europe/Madrid',
  'Europe/Rome',
  'Europe/Warsaw',
  'Europe/Istanbul',
  'Europe/Moscow',
  'Africa/Cairo',
  'Africa/Lagos',
  'Africa/Nairobi',
  'Asia/Dubai',
  'Asia/Karachi',
  'Asia/Kolkata',
  'Asia/Dhaka',
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Australia/Sydney',
  'Australia/Melbourne',
  'Pacific/Auckland',
  'Pacific/Fiji',
]

// ---------------------------------------------------------------------------
// Initials avatar fallback
// ---------------------------------------------------------------------------
function InitialsAvatar({ name, size = 64 }: { name: string; size?: number }) {
  const initials = name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
  return (
    <div
      className="rounded-full bg-primary text-primary-foreground flex items-center justify-center font-semibold select-none"
      style={{ width: size, height: size, fontSize: size * 0.36 }}
      aria-label={`${name} avatar`}
      data-testid="initials-avatar"
    >
      {initials}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ProfilePage
// ---------------------------------------------------------------------------
export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfileResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)

  // Form state
  const [fullName, setFullName] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [tzQuery, setTzQuery] = useState('')
  const [showTzDropdown, setShowTzDropdown] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Avatar state
  const [avatarUploading, setAvatarUploading] = useState(false)
  const [avatarError, setAvatarError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    userApi
      .getMe()
      .then((data) => {
        setProfile(data)
        setFullName(data.full_name)
        setTimezone(data.timezone || 'UTC')
      })
      .catch((err) => {
        setFetchError(err instanceof ApiError ? err.message : 'Failed to load profile.')
      })
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    if (!profile) return
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const updated = await userApi.updateProfile({ full_name: fullName, timezone })
      setProfile(updated)
      setFullName(updated.full_name)
      setTimezone(updated.timezone)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Failed to save profile.')
    } finally {
      setSaving(false)
    }
  }

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !profile) return
    setAvatarError(null)

    // Client-side validation (AC3: PNG/JPG/WebP, max 5MB)
    const allowed = ['image/png', 'image/jpeg', 'image/webp']
    if (!allowed.includes(file.type)) {
      setAvatarError('Only PNG, JPG, and WebP images are supported.')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setAvatarError('Image must be smaller than 5MB.')
      return
    }

    setAvatarUploading(true)
    try {
      // 1. Get presigned URL
      const { upload_url, key } = await userApi.getAvatarUploadUrl({
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      })

      // 2. Upload directly to S3
      const uploadResp = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type },
      })
      if (!uploadResp.ok) throw new Error('Upload failed')

      // 3. Register new URL
      const updated = await userApi.setAvatarUrl(key)
      setProfile(updated)
    } catch (err) {
      setAvatarError(
        err instanceof ApiError ? err.message : 'Avatar upload failed. Please try again.',
      )
    } finally {
      setAvatarUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleRemoveAvatar = async () => {
    if (!profile) return
    setAvatarError(null)
    setAvatarUploading(true)
    try {
      const updated = await userApi.removeAvatar()
      setProfile(updated)
    } catch (err) {
      setAvatarError(err instanceof ApiError ? err.message : 'Failed to remove avatar.')
    } finally {
      setAvatarUploading(false)
    }
  }

  const filteredTimezones = COMMON_TIMEZONES.filter((tz) =>
    tz.toLowerCase().includes(tzQuery.toLowerCase()),
  )

  const isDirty = profile && (fullName !== profile.full_name || timezone !== profile.timezone)

  if (loading) {
    return (
      <div className="flex justify-center py-12" data-testid="profile-loading">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (fetchError) {
    return (
      <div
        role="alert"
        className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
        data-testid="profile-fetch-error"
      >
        {fetchError}
      </div>
    )
  }

  return (
    <div className="space-y-8 max-w-lg" data-testid="profile-page">
      {/* Avatar — AC3 */}
      <section>
        <h3 className="text-base font-medium mb-3">Profile Photo</h3>
        <div className="flex items-center gap-4">
          <div className="relative flex-shrink-0">
            {profile?.avatar_url ? (
              <img
                src={profile.avatar_url}
                alt={`${profile.full_name} avatar`}
                className="h-16 w-16 rounded-full object-cover"
                data-testid="avatar-image"
              />
            ) : (
              <InitialsAvatar name={fullName || profile?.full_name || '?'} size={64} />
            )}
            {avatarUploading && (
              <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center">
                <Loader2 className="h-4 w-4 animate-spin text-white" />
              </div>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={avatarUploading}
                onClick={() => fileInputRef.current?.click()}
                data-testid="change-avatar-btn"
              >
                <Camera className="mr-2 h-4 w-4" />
                Change Photo
              </Button>
              {profile?.avatar_url && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={avatarUploading}
                  onClick={handleRemoveAvatar}
                  className="text-muted-foreground hover:text-destructive"
                  data-testid="remove-avatar-btn"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">PNG, JPG, or WebP · Max 5MB</p>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={handleAvatarChange}
          data-testid="avatar-file-input"
        />
        {avatarError && (
          <p className="mt-2 text-sm text-destructive" data-testid="avatar-error">
            {avatarError}
          </p>
        )}
      </section>

      {/* Name & Email — AC2 */}
      <section className="space-y-4">
        <h3 className="text-base font-medium">Profile Information</h3>

        <div>
          <Label htmlFor="full-name">Full Name</Label>
          <Input
            id="full-name"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Your name"
            maxLength={100}
            className="mt-1"
            data-testid="full-name-input"
          />
        </div>

        <div>
          <Label htmlFor="email">Email Address</Label>
          <div className="mt-1 flex items-center gap-2">
            <Input
              id="email"
              type="email"
              value={profile?.email ?? ''}
              readOnly
              disabled
              className="flex-1 bg-secondary text-muted-foreground"
              data-testid="email-input"
            />
            <span
              className="inline-block px-2 py-1 rounded text-xs font-medium bg-secondary text-muted-foreground border border-border"
              data-testid="auth-provider-badge"
            >
              {profile?.auth_provider === 'google' ? 'Google' : 'Email'}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Email address cannot be changed.
          </p>
        </div>
      </section>

      {/* Timezone — AC4 */}
      <section>
        <h3 className="text-base font-medium mb-3">Timezone</h3>
        <p className="text-sm text-muted-foreground mb-2">
          Used for notification digests and date/time display.
        </p>
        <div className="relative">
          <Input
            type="text"
            value={showTzDropdown ? tzQuery : timezone}
            onChange={(e) => {
              setTzQuery(e.target.value)
              setShowTzDropdown(true)
            }}
            onFocus={() => {
              setTzQuery('')
              setShowTzDropdown(true)
            }}
            onBlur={() => setTimeout(() => setShowTzDropdown(false), 150)}
            placeholder="Search timezone…"
            data-testid="timezone-input"
          />
          {showTzDropdown && filteredTimezones.length > 0 && (
            <ul
              className="absolute z-10 mt-1 w-full max-h-48 overflow-y-auto rounded-md border border-border bg-background shadow-md text-sm"
              data-testid="timezone-dropdown"
            >
              {filteredTimezones.map((tz) => (
                <li
                  key={tz}
                  className={`px-3 py-2 cursor-pointer hover:bg-secondary ${
                    tz === timezone ? 'font-medium bg-secondary/50' : ''
                  }`}
                  onMouseDown={() => {
                    setTimezone(tz)
                    setTzQuery('')
                    setShowTzDropdown(false)
                  }}
                  data-testid={`tz-option-${tz.replace(/\//g, '-')}`}
                >
                  {tz}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* Save — AC2 */}
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
            Profile updated.
          </div>
        )}
        <Button
          onClick={handleSave}
          disabled={!isDirty || saving}
          data-testid="save-profile-btn"
        >
          {saving ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving…</>
          ) : (
            'Save Changes'
          )}
        </Button>
      </section>
    </div>
  )
}
