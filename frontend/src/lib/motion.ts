"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

export function registerGsap() {
  if (typeof window !== "undefined") {
    gsap.registerPlugin(ScrollTrigger);
  }
}

export function motionAllowed() {
  return (
    typeof window !== "undefined" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export { gsap, ScrollTrigger };
