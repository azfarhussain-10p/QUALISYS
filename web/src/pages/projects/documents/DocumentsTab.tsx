/**
 * Documents Tab — Story 2-1-document-upload-parsing
 * AC: #10 — file upload zone (drag-and-drop + click), progress bar, document cards,
 *           parse status badges, polling, delete with confirmation (owner/admin only)
 */

import { useCallback, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, File, FileCode, Trash2, Upload, AlertCircle, CheckCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ApiError, DocumentListItem, documentsApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DocumentsTabProps {
  projectId: string
  projectRole: string | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getFileTypeIcon(fileType: string) {
  switch (fileType) {
    case 'pdf':
      return <FileText className="h-5 w-5 text-red-500" />
    case 'docx':
      return <File className="h-5 w-5 text-blue-500" />
    default:
      return <FileCode className="h-5 w-5 text-green-500" />
  }
}

function ParseStatusBadge({ status, errorMessage }: { status: string; errorMessage?: string | null }) {
  if (status === 'pending' || status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800">
        <Loader2 className="h-3 w-3 animate-spin" />
        Parsing…
      </span>
    )
  }
  if (status === 'completed') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
        <CheckCircle className="h-3 w-3" />
        Ready
      </span>
    )
  }
  // failed
  return (
    <span
      className="inline-flex cursor-help items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800"
      title={errorMessage || 'Parse failed'}
    >
      <AlertCircle className="h-3 w-3" />
      Failed
    </span>
  )
}

// ---------------------------------------------------------------------------
// DocumentCard
// ---------------------------------------------------------------------------

interface DocumentCardProps {
  doc: DocumentListItem
  canDelete: boolean
  onDelete: (id: string) => void
  isDeleting: boolean
}

function DocumentCard({ doc, canDelete, onDelete, isDeleting }: DocumentCardProps) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <div className="flex items-start justify-between rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex min-w-0 gap-3">
        <div className="mt-0.5 shrink-0">{getFileTypeIcon(doc.file_type)}</div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-gray-900">{doc.filename}</p>
          <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
            <span>{doc.file_type.toUpperCase()}</span>
            <span>·</span>
            <span>{formatBytes(doc.file_size_bytes)}</span>
          </div>
          <div className="mt-1.5">
            <ParseStatusBadge status={doc.parse_status} />
          </div>
          {doc.parse_status === 'completed' && doc.preview_text && (
            <p className="mt-2 text-xs text-gray-500 line-clamp-2">{doc.preview_text}</p>
          )}
        </div>
      </div>

      {canDelete && (
        <div className="ml-2 shrink-0">
          {confirmDelete ? (
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="destructive"
                disabled={isDeleting}
                onClick={() => {
                  onDelete(doc.id)
                  setConfirmDelete(false)
                }}
              >
                {isDeleting ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Delete'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setConfirmDelete(false)}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <Button
              size="sm"
              variant="ghost"
              className="text-gray-400 hover:text-red-500"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// DocumentsTab — main component
// ---------------------------------------------------------------------------

export default function DocumentsTab({ projectId, projectRole }: DocumentsTabProps) {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const canDelete = projectRole === 'owner' || projectRole === 'admin'

  // Determine whether any documents are still in a non-terminal state
  const { data, isLoading } = useQuery({
    queryKey: ['documents', projectId],
    queryFn: () => documentsApi.listDocuments(projectId),
    // AC10: poll every 3s while any document is pending/processing (C — refetchInterval not setInterval)
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? []
      const hasPending = items.some(
        (d) => d.parse_status === 'pending' || d.parse_status === 'processing',
      )
      return hasPending ? 3000 : false
    },
  })

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      documentsApi.uploadDocument(projectId, file, (pct) => setUploadProgress(pct)),
    onSuccess: () => {
      setUploadProgress(null)
      setUploadError(null)
      queryClient.invalidateQueries({ queryKey: ['documents', projectId] })
    },
    onError: (err: unknown) => {
      setUploadProgress(null)
      if (err instanceof ApiError) {
        if (err.code === 'FILE_TOO_LARGE') {
          setUploadError('File size exceeds 25MB limit.')
        } else if (err.code === 'UNSUPPORTED_FILE_TYPE') {
          setUploadError('Unsupported file type. Accepted: PDF, DOCX, MD.')
        } else {
          setUploadError(err.message || 'Upload failed. Please try again.')
        }
      } else {
        setUploadError('Upload failed. Please try again.')
      }
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => documentsApi.deleteDocument(projectId, documentId),
    onSuccess: () => {
      setDeletingId(null)
      queryClient.invalidateQueries({ queryKey: ['documents', projectId] })
    },
    onError: () => {
      setDeletingId(null)
    },
  })

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return
      setUploadError(null)
      uploadMutation.mutate(files[0])
    },
    [uploadMutation],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      handleFiles(e.dataTransfer.files)
    },
    [handleFiles],
  )

  const handleDelete = (documentId: string) => {
    setDeletingId(documentId)
    deleteMutation.mutate(documentId)
  }

  return (
    <div className="space-y-6">
      {/* Upload zone — AC10 */}
      <div
        className={`relative flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
          dragOver
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100'
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
        aria-label="Upload document"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.md,.txt"
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
          onClick={(e) => ((e.target as HTMLInputElement).value = '')}
        />
        <Upload className="mb-2 h-8 w-8 text-gray-400" />
        <p className="text-sm font-medium text-gray-700">
          Drag &amp; drop or <span className="text-blue-600">browse</span>
        </p>
        <p className="mt-1 text-xs text-gray-500">PDF, DOCX, MD (max 25MB)</p>

        {/* Upload progress */}
        {uploadProgress !== null && (
          <div className="mt-4 w-full max-w-xs">
            <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
              <span>Uploading…</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-gray-200">
              <div
                className="h-1.5 rounded-full bg-blue-500 transition-all"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Error toast — AC10 */}
      {uploadError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {uploadError}
          <button
            className="ml-auto text-red-500 hover:text-red-700"
            onClick={() => setUploadError(null)}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      {/* Document list */}
      {isLoading && (
        <div className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      )}

      {!isLoading && data?.items.length === 0 && (
        <p className="text-center text-sm text-gray-500 py-8">
          No documents yet. Upload a PDF, DOCX, or Markdown file to get started.
        </p>
      )}

      {!isLoading && data && data.items.length > 0 && (
        <div className="space-y-3">
          {data.items.map((doc) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              canDelete={canDelete}
              onDelete={handleDelete}
              isDeleting={deletingId === doc.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
