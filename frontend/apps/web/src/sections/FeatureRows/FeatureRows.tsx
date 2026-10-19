import { landingContent } from "@/config/content/landing"

export function FeatureRows() {
  const { featureRows } = landingContent

  return (
    <section
      className="mx-auto max-w-[1440px] border-b border-hairline px-4 py-16 sm:px-6 md:px-12 md:py-20"
      id="features-list"
    >
      {/* Header */}
      <div className="mb-12 flex flex-col justify-between text-left md:flex-row md:items-baseline">
        <div>
          <div className="mb-2 font-mono text-[11px] font-medium tracking-wider text-neutral-500 uppercase">
            {featureRows.index}
          </div>
          <h2 className="font-sans text-3xl font-bold tracking-tight text-ink md:text-4xl">
            {featureRows.title}
          </h2>
        </div>
        <p className="mt-4 max-w-md text-left font-serif text-[15px] text-neutral-600 md:mt-0 md:text-[16px]">
          {featureRows.description}
        </p>
      </div>

      {/* Feature Table Rows */}
      <div className="border-t border-hairline">
        {featureRows.items.map((item) => (
          <div
            key={item.name}
            className="grid grid-cols-1 items-center gap-4 border-b border-hairline px-2 py-5 text-left transition-colors duration-150 hover:bg-row-hover md:grid-cols-12"
          >
            <div className="font-sans text-[16px] font-semibold text-ink md:col-span-3 md:text-[18px]">
              {item.name}
            </div>
            <div className="font-serif text-[15px] text-neutral-600 md:col-span-5 md:text-[16px]">
              {item.desc}
            </div>
            <div className="text-left font-mono text-xs md:col-span-4 md:text-right">
              <code
                className={`inline-block border border-hairline px-2 py-1 ${
                  item.isAccent
                    ? "bg-surface-container font-semibold text-accent"
                    : "bg-surface-container text-ink"
                }`}
              >
                {item.example}
              </code>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
