import { useState, type FormEvent } from "react"
import { Eye, EyeOff } from "lucide-react"
import { Logo } from "@/components/Logo"
import { loginContent } from "@/config/content/login"
import { LoginCanvas } from "@/sections/Login/LoginCanvas"
import { signIn, signUp } from "@/api/auth"

interface LoginPageProps {
  onNavigateLanding?: () => void
  onNavigateDashboard?: () => void
}

export function LoginPage({
  onNavigateLanding,
  onNavigateDashboard,
}: LoginPageProps) {
  const [isRegister, setIsRegister] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null)

  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [rememberDaemon, setRememberDaemon] = useState(true)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)
    setNoticeMessage(null)
    setIsLoading(true)

    try {
      if (isRegister) {
        const result = await signUp(
          fullName,
          email,
          password,
          rememberDaemon,
        )
        if (result.needsEmailConfirmation) {
          setNoticeMessage(
            "Account created. Check your email to confirm it, then sign in.",
          )
          setIsRegister(false)
          return
        }
      } else {
        await signIn(email, password, rememberDaemon)
      }

      onNavigateDashboard?.()
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Authentication failed",
      )
    } finally {
      setIsLoading(false)
    }
  }

  const activeContent = isRegister ? loginContent.register : loginContent.signIn

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col border-x border-hairline bg-paper font-serif text-ink antialiased selection:bg-accent selection:text-paper lg:flex-row">
      {/* LEFT PANE: 45% Authentication Sheet */}
      <section className="relative z-10 flex w-full flex-col justify-between border-b border-hairline bg-paper p-6 text-left sm:p-10 lg:w-[45%] lg:border-r lg:border-b-0 lg:p-12 xl:p-14">
        {/* Top Bar / Brand Anchor & Back Nav */}
        <div className="flex items-center justify-between border-b border-hairline pb-8">
          <div className="flex items-center gap-3">
            <Logo showText={false} />
            <div className="flex flex-col">
              <span className="font-sans text-xs font-bold tracking-[0.14em] text-ink uppercase">
                {loginContent.brand}
              </span>
              <span className="font-mono text-[9px] tracking-widest text-neutral-500 uppercase">
                {loginContent.engineSubtitle}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onNavigateLanding}
            className="group inline-flex cursor-pointer items-center gap-1.5 font-mono text-xs text-ink transition-colors duration-150 hover:text-accent"
          >
            <span className="transition-transform duration-150 group-hover:-translate-x-1">
              ←
            </span>
            <span className="underline decoration-hairline underline-offset-4 group-hover:decoration-accent">
              {loginContent.backToLanding}
            </span>
          </button>
        </div>

        {/* Main Form Sheet Content */}
        <div className="mx-auto w-full max-w-[440px] py-8 lg:py-10">
          {/* Form Header: Dual-Weight Hierarchy */}
          <div className="mb-8">
            <h1 className="mb-3 text-left leading-[1.1]">
              <span
                className="block font-sans text-3xl font-light tracking-tight text-ink sm:text-4xl md:text-5xl"
                style={{ fontWeight: "var(--headline-weight-contrast, 300)" }}
              >
                {activeContent.titleLight}
              </span>
              <span className="block font-sans text-3xl font-bold tracking-tight text-ink sm:text-4xl md:text-5xl">
                {activeContent.titleBold}
              </span>
            </h1>
            <p className="text-left font-serif text-[15px] leading-relaxed text-neutral-600 sm:text-[16px]">
              {activeContent.subtext}
            </p>
          </div>

          {/* Inline Error Banner if triggered */}
          {errorMessage && (
            <div className="mb-6 border-y border-r border-l-2 border-red-200/50 border-red-600 bg-red-50/70 p-3">
              <p className="font-mono text-[11px] font-semibold tracking-tight text-red-900">
                {errorMessage}
              </p>
            </div>
          )}

          {noticeMessage && (
            <div className="mb-6 border-y border-r border-l-2 border-hairline border-l-accent bg-surface-white p-3">
              <p className="font-mono text-[11px] font-semibold tracking-tight text-ink">
                {noticeMessage}
              </p>
            </div>
          )}

          {/* Authentication Form */}
          <form className="space-y-6" onSubmit={handleSubmit}>
            {/* Registration field: Full Name */}
            {isRegister && (
              <div className="relative pt-2 text-left">
                <label
                  htmlFor="full-name"
                  className="mb-1 block font-mono text-[10px] tracking-wider text-neutral-500 uppercase"
                >
                  {loginContent.fields.fullName.label}
                </label>
                <input
                  id="full-name"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder={loginContent.fields.fullName.placeholder}
                  className="w-full border-0 border-b border-hairline bg-transparent px-0 py-2 font-sans text-sm text-ink transition-colors placeholder:text-neutral-400 focus:border-b-2 focus:border-accent focus:outline-none"
                />
              </div>
            )}

            {/* Field 1: Work Email with Underline-only hairline */}
            <div className="relative pt-2 text-left">
              <div className="mb-1 flex items-center justify-between">
                <label
                  htmlFor="work-email"
                  className="block font-mono text-[10px] font-semibold tracking-wider text-neutral-500 uppercase"
                >
                  {loginContent.fields.workEmail.label}
                </label>
                <span className="font-mono text-[10px] text-neutral-400">
                  {loginContent.fields.workEmail.badge}
                </span>
              </div>
              <input
                id="work-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={loginContent.fields.workEmail.placeholder}
                className="w-full border-0 border-b border-hairline bg-transparent px-0 py-2 font-sans text-sm text-ink transition-colors placeholder:text-neutral-400 focus:border-b-2 focus:border-accent focus:outline-none"
              />
            </div>

            {/* Field 2: Password with Underline & Toggle button */}
            <div className="relative pt-2 text-left">
              <div className="mb-1 flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="block font-mono text-[10px] font-semibold tracking-wider text-neutral-500 uppercase"
                >
                  {loginContent.fields.password.label}
                </label>
                {!isRegister && (
                  <button
                    type="button"
                    onClick={() =>
                      alert(
                        "Password reset link will be sent to your verified domain."
                      )
                    }
                    className="cursor-pointer font-serif text-xs text-ink underline decoration-hairline underline-offset-2 transition-colors hover:text-accent"
                  >
                    {loginContent.fields.password.forgotLink}
                  </button>
                )}
              </div>
              <div className="relative flex items-center">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={loginContent.fields.password.placeholder}
                  className="w-full border-0 border-b border-hairline bg-transparent px-0 py-2 pr-8 font-mono text-sm tracking-wider text-ink transition-colors placeholder:text-neutral-400 focus:border-b-2 focus:border-accent focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute top-1/2 right-0 -translate-y-1/2 cursor-pointer p-1 text-neutral-500 transition-colors hover:text-ink"
                  title="Toggle password visibility"
                >
                  {showPassword ? (
                    <EyeOff className="size-4" strokeWidth={1.5} />
                  ) : (
                    <Eye className="size-4" strokeWidth={1.5} />
                  )}
                </button>
              </div>
            </div>

            {/* Remember local daemon token */}
            <div className="flex items-center justify-between pt-1 text-left">
              <label className="flex cursor-pointer items-center gap-2.5 select-none">
                <input
                  type="checkbox"
                  checked={rememberDaemon}
                  onChange={(e) => setRememberDaemon(e.target.checked)}
                  className="size-3.5 cursor-pointer rounded-[0px] border border-ink text-ink accent-ink"
                />
                <span className="font-mono text-[11px] text-neutral-600">
                  {loginContent.fields.rememberDaemon}
                </span>
              </label>
              <span className="font-mono text-[10px] text-neutral-400">
                {loginContent.fields.ttl}
              </span>
            </div>

            {/* Primary CTA Button with Progress line simulation */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={isLoading}
                className="group flex w-full cursor-pointer items-center justify-center gap-2 rounded-[2px] bg-ink px-6 py-3.5 font-sans text-xs font-bold tracking-[0.12em] text-paper uppercase transition-all duration-150 hover:bg-[#2A2A30] active:bg-accent disabled:opacity-75"
              >
                {isLoading ? (
                  <span className="font-mono text-xs text-paper">
                    {loginContent.loadingStatus}
                  </span>
                ) : (
                  <>
                    <span>{activeContent.submitLabel}</span>
                    <span className="transition-transform duration-150 group-hover:translate-x-1">
                      →
                    </span>
                  </>
                )}
              </button>
            </div>

            {/* Switch Auth Mode Link */}
            <div className="pt-1 text-center">
              <button
                type="button"
                onClick={() => {
                  setIsRegister(!isRegister)
                  setErrorMessage(null)
                  setNoticeMessage(null)
                }}
                className="group inline-flex cursor-pointer items-center gap-1 font-serif text-sm text-ink transition-colors hover:text-accent"
              >
                <span className="underline decoration-hairline underline-offset-4 group-hover:decoration-accent">
                  {isRegister
                    ? loginContent.modeSwitch.toSignIn
                    : loginContent.modeSwitch.toRegister}
                </span>
                <span className="transition-transform group-hover:translate-x-0.5">
                  →
                </span>
              </button>
            </div>
          </form>

          {/* Offline / Air-Gapped Alternative Box */}
          <div className="mt-10 border-t border-hairline pt-8 text-left">
            <div className="mb-3 flex items-center justify-between">
              <span className="font-mono text-[10px] font-semibold tracking-wider text-neutral-500 uppercase">
                {loginContent.localAlternative.badge}
              </span>
              <div className="flex items-center gap-1.5">
                <span className="inline-block size-1.5 shrink-0 rotate-45 bg-gold" />
                <span className="font-mono text-[9px] font-medium tracking-wider text-gold uppercase">
                  {loginContent.localAlternative.tag}
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={onNavigateLanding}
              className="group w-full cursor-pointer rounded-[0px] border border-hairline bg-surface-white p-4 text-left transition-colors duration-150 hover:bg-row-hover"
            >
              <div className="flex items-center justify-between">
                <span className="font-sans text-xs font-semibold tracking-wider text-ink uppercase">
                  {loginContent.localAlternative.title}
                </span>
                <span className="font-sans text-sm text-ink transition-transform group-hover:translate-x-1">
                  →
                </span>
              </div>
              <p className="mt-2 flex items-center gap-2 font-mono text-[11px] text-neutral-500">
                {loginContent.localAlternative.bullets.map((bullet, idx) => (
                  <span key={bullet} className="flex items-center gap-2">
                    {idx > 0 && <span className="text-hairline">/</span>}
                    <span>{bullet}</span>
                  </span>
                ))}
              </p>
            </button>
          </div>
        </div>

        {/* Bottom Micro Footer */}
        <div className="flex flex-col items-start justify-between gap-2 border-t border-hairline pt-6 text-neutral-500 sm:flex-row sm:items-center">
          <span className="font-mono text-[10px]">
            {loginContent.footer.copyright}
          </span>
          <div className="flex items-center gap-4 font-mono text-[10px]">
            {loginContent.footer.links.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="underline decoration-hairline underline-offset-2 transition-colors hover:text-accent"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>
      </section>

      {/* RIGHT PANE: 55% Matte Black Deep Analysis Canvas */}
      <LoginCanvas />
    </div>
  )
}
