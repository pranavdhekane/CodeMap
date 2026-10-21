import { useState, useRef, useEffect } from "react"
import { Search, ChevronDown, Check } from "lucide-react"
import { dashboardContent } from "@/config/content/dashboard"

export type SortCriteria = "RECENT" | "NAME_ASC" | "CYCLES" | "SIZE"
export type ScopeFilter = "ALL" | "MINE"

interface FilterBarProps {
  searchQuery: string
  onSearchChange: (query: string) => void
  activeScope: ScopeFilter
  onScopeChange: (scope: ScopeFilter) => void
  activeSort: SortCriteria
  onSortChange: (sort: SortCriteria) => void
  countAll: number
  countMine: number
}

export function FilterBar({
  searchQuery,
  onSearchChange,
  activeScope,
  onScopeChange,
  activeSort,
  onSortChange,
  countAll,
  countMine,
}: FilterBarProps) {
  const { filters } = dashboardContent
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const currentSortOption =
    filters.sortOptions.find((opt) => opt.id === activeSort) ||
    filters.sortOptions[0]

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  return (
    <section className="my-2 flex flex-col items-stretch justify-between gap-4 border-y border-hairline py-3.5 md:flex-row md:items-center">
      {/* Underline Search Input */}
      <div className="relative flex max-w-lg flex-grow items-center gap-3">
        <Search
          className="size-[18px] text-neutral-400 transition-colors"
          strokeWidth={1.5}
        />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={filters.searchPlaceholder}
          className="w-full border-0 border-b border-hairline bg-transparent py-1 font-mono text-[13px] text-ink placeholder:text-neutral-400 focus:border-b-2 focus:border-accent focus:outline-none"
        />
      </div>

      {/* Scope and Sort Controls */}
      <div className="relative flex items-center gap-3 self-end md:self-auto">
        {/* Scope Pills */}
        <div className="flex items-center rounded-[1px] border border-hairline bg-surface-container-low p-0.5">
          <button
            type="button"
            onClick={() => onScopeChange("ALL")}
            className={`cursor-pointer px-3 py-1 font-mono text-[10px] font-semibold tracking-wider uppercase transition-colors duration-150 ${
              activeScope === "ALL"
                ? "bg-ink text-paper"
                : "text-neutral-600 hover:text-ink"
            }`}
          >
            {filters.scopeAll} ({countAll})
          </button>
          <button
            type="button"
            onClick={() => onScopeChange("MINE")}
            className={`cursor-pointer px-3 py-1 font-mono text-[10px] font-semibold tracking-wider uppercase transition-colors duration-150 ${
              activeScope === "MINE"
                ? "bg-ink text-paper"
                : "text-neutral-600 hover:text-ink"
            }`}
          >
            {filters.scopeMine} ({countMine})
          </button>
        </div>

        {/* Sort Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setIsDropdownOpen((prev) => !prev)}
            className="flex cursor-pointer items-center gap-2 rounded-[1px] border border-hairline bg-paper px-3 py-1.5 font-mono text-[11px] tracking-wider text-ink uppercase transition-colors hover:bg-row-hover"
          >
            <span>{currentSortOption.display}</span>
            <ChevronDown
              className={`size-3 transition-transform duration-150 ${
                isDropdownOpen ? "rotate-180" : ""
              }`}
              strokeWidth={1.5}
            />
          </button>

          {isDropdownOpen && (
            <div className="absolute right-0 z-30 mt-1 w-44 rounded-[1px] border border-hairline bg-paper py-1 font-mono text-[11px] shadow-sm">
              {filters.sortOptions.map((opt) => {
                const isSelected = opt.id === activeSort
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => {
                      onSortChange(opt.id as SortCriteria)
                      setIsDropdownOpen(false)
                    }}
                    className="flex w-full cursor-pointer items-center justify-between px-3 py-1.5 text-left text-ink transition-colors hover:bg-row-hover"
                  >
                    <span>{opt.label}</span>
                    {isSelected && (
                      <Check className="size-3 text-accent" strokeWidth={2} />
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
