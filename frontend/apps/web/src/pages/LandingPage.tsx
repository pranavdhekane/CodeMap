import { Navbar } from "@/sections/Navbar/Navbar"
import { HeroSection } from "@/sections/Hero/HeroSection"
import { PrivacyStrip } from "@/sections/PrivacyStrip/PrivacyStrip"
import { ArchitecturePipeline } from "@/sections/Architecture/ArchitecturePipeline"
import { FeatureShowcase } from "@/sections/FeatureShowcase/FeatureShowcase"
import { FeatureRows } from "@/sections/FeatureRows/FeatureRows"
import { ExecutionModes } from "@/sections/ExecutionModes/ExecutionModes"
import { FinalCta } from "@/sections/FinalCta/FinalCta"
import { Footer } from "@/sections/Footer/Footer"
import { TweaksPanel } from "@/components/TweaksPanel"

interface LandingPageProps {
  onNavigateLogin?: () => void
  onNavigateDashboard?: () => void
}

export function LandingPage({
  onNavigateLogin,
  onNavigateDashboard,
}: LandingPageProps) {
  return (
    <div className="min-h-screen overflow-x-hidden bg-paper font-serif text-ink antialiased selection:bg-accent selection:text-paper">
      <Navbar
        onNavigateLogin={onNavigateLogin}
        onNavigateDashboard={onNavigateDashboard}
      />
      <main>
        <HeroSection onAnalyze={onNavigateDashboard} />
        <PrivacyStrip />
        <ArchitecturePipeline />
        <FeatureShowcase />
        <FeatureRows />
        <ExecutionModes
          onNavigateLogin={onNavigateLogin}
          onNavigateDashboard={onNavigateDashboard}
        />
        <FinalCta onAnalyze={onNavigateDashboard} />
      </main>
      <Footer />
      <TweaksPanel />
    </div>
  )
}
