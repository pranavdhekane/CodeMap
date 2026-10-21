import React, { useEffect, useState } from "react"
import { landingContent } from "@/config/content/landing"
import { useReducedMotion } from "@/hooks/useReducedMotion"

export function PrivacyStrip() {
  const { command, bullets } = landingContent.privacyStrip
  const prefersReduced = useReducedMotion()
  const [displayText, setDisplayText] = useState(() =>
    prefersReduced ? command : ""
  )

  useEffect(() => {
    if (prefersReduced) return

    let charIdx = 0
    const timer = setInterval(() => {
      charIdx++
      setDisplayText(command.slice(0, charIdx))
      if (charIdx >= command.length) {
        clearInterval(timer)
      }
    }, 45)

    return () => clearInterval(timer)
  }, [command, prefersReduced])

  return (
    <section
      className="w-full border-b border-hairline bg-surface-white"
      id="privacy-bar"
    >
      <div className="mx-auto flex max-w-[1440px] flex-col justify-between gap-4 px-4 py-3.5 font-mono text-xs sm:px-6 md:flex-row md:items-center md:px-12">
        {/* Terminal Line */}
        <div className="flex items-center gap-2 text-ink">
          <span className="text-neutral-400 select-none">$</span>
          <span className="font-medium tracking-tight text-ink">
            {prefersReduced ? command : displayText}
          </span>
          <span className="cursor-blink inline-block h-3.5 w-1.5 bg-ink select-none" />
        </div>

        {/* Assertions */}
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-neutral-500">
          <span className="inline-block size-1.5 shrink-0 bg-gold" />
          {bullets.map((bullet, idx) => (
            <React.Fragment key={bullet}>
              {idx > 0 && <span className="text-hairline">|</span>}
              <span
                className={
                  bullet.includes("0 bytes")
                    ? "font-semibold text-accent"
                    : "text-neutral-600"
                }
              >
                {bullet}
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>
    </section>
  )
}
