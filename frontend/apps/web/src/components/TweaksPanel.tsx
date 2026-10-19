import { useState, type ChangeEvent } from "react"
import { useTheme } from "./theme-provider"

const ACCENT_COLORS = [
  { label: "Royal Violet", hex: "#4B2BB5" },
  { label: "Emerald", hex: "#1B5E20" },
  { label: "Antique Gold", hex: "#B8923A" },
  { label: "Indigo", hex: "#1A237E" },
]

export function TweaksPanel() {
  const [isOpen, setIsOpen] = useState(false)
  const [activeAccent, setActiveAccent] = useState("#4B2BB5")
  const [headlineWeight, setHeadlineWeight] = useState(300)
  const [motionActive, setMotionActive] = useState(true)
  const { theme, setTheme } = useTheme()

  const handleAccentChange = (hex: string) => {
    setActiveAccent(hex)
    document.documentElement.style.setProperty("--editorial-accent", hex)
  }

  const handleWeightChange = (e: ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value)
    setHeadlineWeight(val)
    document.documentElement.style.setProperty(
      "--headline-weight-contrast",
      val.toString()
    )
  }

  const handleMotionToggle = () => {
    const next = !motionActive
    setMotionActive(next)
    const pulses = document.querySelectorAll<HTMLElement>(
      ".cycle-highlight-pulse"
    )
    pulses.forEach((el) => {
      el.style.animation = next
        ? "cyclePulse 8s cubic-bezier(0.4, 0, 0.6, 1) infinite"
        : "none"
    })
  }

  const isDark =
    theme === "dark" ||
    (theme === "system" &&
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches)

  return (
    <aside
      className="fixed right-4 bottom-4 z-50 select-none"
      id="tweaks-panel"
      aria-label="Studio Controls"
    >
      {/* Collapsible Trigger Pill */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex cursor-pointer items-center gap-2 rounded-[2px] border border-hairline bg-ink px-3 py-2 font-mono text-xs text-paper shadow-none transition-colors hover:bg-[#2A2A30]"
        aria-expanded={isOpen}
      >
        <span className="inline-block size-2 shrink-0 bg-gold" />
        <span>STUDIO CONTROLS</span>
        <span className="text-[10px]">{isOpen ? "▼" : "▲"}</span>
      </button>

      {/* Controls Body Drawer */}
      {isOpen && (
        <div className="mt-2 w-72 rounded-[0px] border border-ink bg-surface-white p-4 font-mono text-xs text-ink">
          <div className="mb-3 flex items-center justify-between border-b border-hairline pb-2">
            <span className="text-[10px] font-bold tracking-wider uppercase">
              Display Preferences
            </span>
            <span className="text-[10px] text-neutral-500">DEV TOOL</span>
          </div>

          {/* Accent Hue Swatches */}
          <div className="mb-4">
            <label className="mb-2 block text-[10px] tracking-wider text-neutral-500 uppercase">
              Accent Hue
            </label>
            <div className="flex items-center gap-2">
              {ACCENT_COLORS.map((col) => (
                <button
                  key={col.hex}
                  type="button"
                  title={col.label}
                  onClick={() => handleAccentChange(col.hex)}
                  className={`size-6 cursor-pointer rounded-[0px] transition-transform ${
                    activeAccent === col.hex
                      ? "scale-110 border-2 border-ink"
                      : "border border-hairline hover:border-ink"
                  }`}
                  style={{ backgroundColor: col.hex }}
                />
              ))}
            </div>
          </div>

          {/* Headline Weight Slider */}
          <div className="mb-4">
            <div className="mb-1 flex justify-between text-[10px] tracking-wider text-neutral-500 uppercase">
              <span>Light Contrast</span>
              <span>{headlineWeight}</span>
            </div>
            <input
              type="range"
              min={200}
              max={400}
              step={100}
              value={headlineWeight}
              onChange={handleWeightChange}
              className="w-full cursor-pointer accent-ink"
            />
          </div>

          {/* Motion Toggle */}
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[10px] tracking-wider text-neutral-500 uppercase">
              Cycle Pulse Motion
            </span>
            <button
              type="button"
              onClick={handleMotionToggle}
              className={`cursor-pointer rounded-[2px] px-2 py-0.5 text-[10px] font-bold uppercase ${
                motionActive
                  ? "border border-ink bg-ink text-paper"
                  : "border border-hairline text-neutral-600"
              }`}
            >
              {motionActive ? "ENABLED" : "PAUSED"}
            </button>
          </div>

          {/* Theme Inversion Toggle */}
          <div className="flex items-center justify-between border-t border-hairline pt-3">
            <span className="text-[10px] tracking-wider text-neutral-500 uppercase">
              Theme Mode
            </span>
            <button
              type="button"
              onClick={() => setTheme(isDark ? "light" : "dark")}
              className="cursor-pointer rounded-[2px] border border-hairline px-2 py-0.5 text-[10px] uppercase hover:border-ink"
            >
              {isDark ? "DARK" : "LIGHT"}
            </button>
          </div>
        </div>
      )}
    </aside>
  )
}
