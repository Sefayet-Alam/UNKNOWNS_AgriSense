"use client";

import { useGSAP } from "@gsap/react";
import { useRef } from "react";
import { gsap, motionAllowed, registerGsap } from "@/lib/motion";

interface Props {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "li" | "section";
  y?: number;
}

export function Reveal({ children, delay = 0, className = "", as = "div", y = 28 }: Props) {
  const ref = useRef<HTMLElement | null>(null);

  useGSAP(
    () => {
      registerGsap();
      if (!motionAllowed() || !ref.current) return;
      gsap.fromTo(
        ref.current,
        { y },
        {
          y: 0,
          delay: delay / 1000,
          duration: 0.76,
          ease: "power3.out",
          scrollTrigger: {
            trigger: ref.current,
            start: "top 90%",
            once: true,
          },
        },
      );
    },
    { scope: ref, dependencies: [delay, y] },
  );

  const Tag = as as "div";
  return (
    <Tag
      ref={ref as React.RefObject<HTMLDivElement>}
      className={className}
    >
      {children}
    </Tag>
  );
}
