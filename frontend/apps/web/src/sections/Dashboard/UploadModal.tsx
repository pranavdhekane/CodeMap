import {
  useState,
  useRef,
  useEffect,
  useCallback,
  type DragEvent,
  type ChangeEvent,
} from "react"
import { Upload, FileArchive, X, AlertCircle } from "lucide-react"
import { Button } from "@workspace/ui/components/button"
import { dashboardContent, type DummyProject } from "@/config/content/dashboard"
import { uploadProjectZip, projectItemToUi } from "@/api/projects"

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
  onProjectCreated: (newProject: DummyProject) => void
}

type ModalStage = "IDLE" | "SELECTED" | "LOADING"

export function UploadModal({
  isOpen,
  onClose,
  onProjectCreated,
}: UploadModalProps) {
  const { uploadModal } = dashboardContent

  const [stage, setStage] = useState<ModalStage>("IDLE")
  const [projectName, setProjectName] = useState("")
  const [rawFile, setRawFile] = useState<File | null>(null)
  const [selectedFile, setSelectedFile] = useState<{
    name: string
    sizeFormatted: string
    sizeBytes: number
  } | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [loadingProgress, setLoadingProgress] = useState(20)
  const [logIndex, setLogIndex] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleResetAndClose = useCallback(() => {
    setStage("IDLE")
    setRawFile(null)
    setSelectedFile(null)
    setErrorMessage(null)
    setProjectName("")
    onClose()
  }, [onClose])

  // Handle escape key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && stage !== "LOADING") {
        handleResetAndClose()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [handleResetAndClose, stage])

  if (!isOpen) return null

  const handleFileChosen = (file: File) => {
    if (!file.name.toLowerCase().endsWith(".zip")) {
      setErrorMessage("Please select a .zip archive containing Python code.")
      return
    }

    setErrorMessage(null)
    setRawFile(file)
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1)
    const formatted =
      file.size > 1024 * 1024
        ? `${sizeMb} MB`
        : `${Math.round(file.size / 1024)} KB`

    setSelectedFile({
      name: file.name,
      sizeFormatted: formatted,
      sizeBytes: file.size,
    })

    if (!projectName.trim()) {
      const cleanName = file.name.replace(/\.zip$/i, "")
      setProjectName(cleanName)
    }

    setStage("SELECTED")
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChosen(e.dataTransfer.files[0])
    }
  }

  const handleNativeChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileChosen(e.target.files[0])
    }
  }

  const handleStartAnalysis = async () => {
    if (stage === "IDLE") {
      fileInputRef.current?.click()
      return
    }

    if (stage === "SELECTED" && rawFile) {
      setStage("LOADING")
      setLoadingProgress(25)
      setLogIndex(0)
      setErrorMessage(null)

      const timer = setInterval(() => {
        setLoadingProgress((prev) => {
          if (prev < 80) {
            const next = prev + 14
            if (next >= 40 && next < 65) setLogIndex(2)
            if (next >= 65) setLogIndex(3)
            return next
          }
          return prev
        })
      }, 250)

      try {
        const createdProject = await uploadProjectZip(rawFile, projectName)
        clearInterval(timer)
        setLoadingProgress(100)
        setLogIndex(4)

        const uiProject = projectItemToUi(createdProject, 0)
        setTimeout(() => {
          onProjectCreated(uiProject)
          handleResetAndClose()
        }, 500)
      } catch (err: unknown) {
        clearInterval(timer)
        setStage("SELECTED")
        const message = err instanceof Error ? err.message : "Failed to analyze project archive"
        setErrorMessage(message)
      }
    }
  }

  const filledBlocks = Math.floor(loadingProgress / 10)
  const emptyBlocks = Math.max(0, 10 - filledBlocks)
  const asciiBar = `[${"■".repeat(filledBlocks)}${"□".repeat(emptyBlocks)}]`

  return (
    <div
      onClick={handleResetAndClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#0E0E10]/35 p-4 transition-opacity"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative flex w-full max-w-[560px] flex-col gap-6 rounded-[2px] border border-hairline bg-paper p-6 text-left transition-all md:p-8"
      >
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <span className="font-mono text-[10px] tracking-widest text-neutral-500 uppercase">
              {uploadModal.tag}
            </span>
            <h3 className="font-sans text-xl font-bold tracking-tight text-ink md:text-2xl">
              {uploadModal.title}
            </h3>
          </div>
          <button
            type="button"
            onClick={handleResetAndClose}
            aria-label={uploadModal.closeAria}
            className="flex size-8 cursor-pointer items-center justify-center border border-hairline font-sans text-sm text-ink transition-colors hover:bg-row-hover"
          >
            <X className="size-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* Error message */}
        {errorMessage && (
          <div className="flex items-start gap-2 border border-red-500/30 bg-red-50 p-3 text-red-800">
            <AlertCircle className="size-4 shrink-0 mt-0.5 text-red-600" />
            <p className="font-mono text-[12px] leading-tight">{errorMessage}</p>
          </div>
        )}

        {/* Form Field: Project Name */}
        <div className="space-y-1.5">
          <label
            htmlFor="project-name-input"
            className="block font-mono text-[11px] font-bold tracking-wider text-ink uppercase"
          >
            {uploadModal.slugLabel}
          </label>
          <input
            id="project-name-input"
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            disabled={stage === "LOADING"}
            placeholder={uploadModal.slugPlaceholder}
            className="w-full border-0 border-b border-hairline bg-transparent py-1.5 font-mono text-[14px] text-ink placeholder:text-neutral-400 focus:border-b-2 focus:border-accent focus:outline-none"
          />
        </div>

        {/* Modal Stage 1: Idle Dropzone */}
        {stage === "IDLE" && (
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`flex cursor-pointer flex-col items-center justify-center rounded-[2px] border border-dashed p-8 text-center transition-colors ${
              isDragOver
                ? "border-accent bg-surface-container-low"
                : "border-hairline bg-surface-container-low/40 hover:border-accent hover:bg-surface-container-low"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              onChange={handleNativeChange}
              className="hidden"
            />
            <Upload className="mb-3 size-7 text-ink" strokeWidth={1.5} />
            <p className="mb-1 font-serif text-base font-medium text-ink">
              {uploadModal.dropzone.idlePrimary}{" "}
              <span className="border border-hairline bg-surface-container px-1 py-0.5 font-mono text-[13px]">
                {uploadModal.dropzone.idleBadge}
              </span>{" "}
              {uploadModal.dropzone.idleSecondary}
            </p>
            <p className="font-mono text-[11px] text-neutral-500">
              {uploadModal.dropzone.constraint}
            </p>
          </div>
        )}

        {/* Modal Stage 2: File Selected */}
        {stage === "SELECTED" && selectedFile && (
          <div className="flex items-center justify-between border border-hairline bg-surface-white p-4">
            <div className="flex items-center gap-3">
              <FileArchive
                className="size-6 shrink-0 text-ink"
                strokeWidth={1.5}
              />
              <div className="flex flex-col">
                <span className="font-mono text-[12px] font-bold text-ink">
                  {selectedFile.name}
                </span>
                <span className="font-mono text-[10px] text-neutral-500">
                  {selectedFile.sizeFormatted} ·{" "}
                  {uploadModal.fileSelected.metaSuffix}
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                setRawFile(null)
                setSelectedFile(null)
                setStage("IDLE")
              }}
              className="cursor-pointer border border-hairline px-2 py-1 font-mono text-[11px] text-ink transition-colors hover:border-red-600 hover:bg-red-50 hover:text-red-700"
            >
              {uploadModal.fileSelected.removeBtn}
            </button>
          </div>
        )}

        {/* Modal Stage 3: Loading Chamber */}
        {stage === "LOADING" && (
          <div className="flex flex-col gap-3 border border-hairline bg-[#0E0E10] p-5 text-paper">
            <div className="flex items-center justify-between font-mono text-[11px]">
              <span className="flex items-center gap-2 text-gold">
                <span className="size-2 bg-gold" />
                {uploadModal.loading.status}
              </span>
              <span className="font-mono text-neutral-400">
                {loadingProgress}%
              </span>
            </div>

            {/* Terminal Stream Log */}
            <div className="font-mono text-[12px] leading-5 tracking-tight text-neutral-300">
              {uploadModal.loading.logs
                .slice(0, logIndex + 1)
                .map((line, idx) => (
                  <p
                    key={line}
                    className={
                      idx === logIndex ? "text-gold" : "text-neutral-400"
                    }
                  >
                    {line}
                  </p>
                ))}
            </div>

            {/* Progress Bar & ASCII indicator */}
            <div className="mt-1 space-y-1">
              <div className="h-1.5 w-full overflow-hidden bg-neutral-800">
                <div
                  className="h-full bg-accent transition-all duration-300 ease-out"
                  style={{ width: `${loadingProgress}%` }}
                />
              </div>
              <div className="flex justify-between pt-0.5 font-mono text-[10px] text-neutral-400">
                <span>{asciiBar}</span>
                <span>{uploadModal.loading.verified}</span>
              </div>
            </div>
          </div>
        )}

        {/* Privacy Strip: Highlight that only analysis is stored, code is discarded */}
        <div className="flex items-center justify-between border border-hairline bg-surface-container-low/60 p-3 font-mono text-[11px]">
          <div className="flex items-center gap-2 truncate">
            <span className="text-gold">◆</span>
            <span className="truncate text-ink">
              Privacy First: Only AST analysis & metrics are stored. Raw code is never retained.
            </span>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button
            variant="outline"
            onClick={handleResetAndClose}
            disabled={stage === "LOADING"}
            className="cursor-pointer border-hairline px-4 py-2.5 font-sans text-[11px] font-bold tracking-wider text-ink uppercase hover:border-ink hover:bg-row-hover"
          >
            {uploadModal.cancelBtn}
          </Button>

          <Button
            onClick={handleStartAnalysis}
            disabled={stage === "LOADING"}
            className="group cursor-pointer gap-2 rounded-[2px] bg-ink px-5 py-2.5 font-sans text-[11px] font-bold tracking-[0.12em] text-paper uppercase hover:bg-[#2A2A30]"
          >
            {stage === "LOADING" ? (
              <span>
                {uploadModal.submitLoadingPrefix} {asciiBar} {loadingProgress}%
              </span>
            ) : stage === "SELECTED" ? (
              <>
                <span>{uploadModal.submitReady}</span>
                <span className="transition-transform duration-150 group-hover:translate-x-1">
                  →
                </span>
              </>
            ) : (
              <>
                <span>Choose .zip Archive</span>
                <span className="transition-transform duration-150 group-hover:translate-x-1">
                  →
                </span>
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
