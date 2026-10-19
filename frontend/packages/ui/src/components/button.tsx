import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 cursor-pointer items-center justify-center rounded-[2px] border border-transparent font-sans text-[11px] font-bold tracking-wider uppercase transition-colors duration-150 outline-none select-none focus-visible:ring-1 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
  {
    variants: {
      variant: {
        default:
          "border-ink bg-ink text-paper hover:bg-[#2A2A30] active:bg-accent",
        outline:
          "border-ink bg-transparent text-ink hover:bg-ink hover:text-paper",
        secondary:
          "border-hairline bg-surface-container text-ink hover:border-ink hover:bg-surface-white",
        ghost: "border-transparent text-ink hover:bg-surface-container",
        destructive: "bg-destructive text-white hover:bg-destructive/90",
        link: "h-auto border-transparent p-0 font-serif tracking-normal text-ink normal-case underline decoration-ink underline-offset-4 hover:text-accent hover:decoration-accent",
      },
      size: {
        default: "h-9 gap-1.5 px-4 py-2",
        sm: "h-7 gap-1 px-3 py-1 text-[10px]",
        lg: "h-11 gap-2 px-6 py-3 text-xs",
        icon: "size-8 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
