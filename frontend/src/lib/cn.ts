import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names, letting later Tailwind utilities win over earlier ones.
 *
 * Plain string concatenation puts `px-2 px-4` in the class list and leaves the
 * winner to CSS source order, which is not the order they were written in. That
 * makes a component's `className` prop unreliable as an override -- the whole
 * point of accepting one.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
