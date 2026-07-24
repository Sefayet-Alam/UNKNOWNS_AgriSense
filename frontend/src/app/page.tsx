"use client";

import { useGSAP } from "@gsap/react";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CalendarRange,
  CloudSun,
  CircleDollarSign,
  MapPinned,
  MessageSquareText,
  RefreshCcw,
  ShieldCheck,
  Sprout,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import FieldAtlasScene from "@/components/home/FieldAtlasScene";
import { Reveal } from "@/components/home/Reveal";
import { Logo, LogoMark } from "@/components/ui/Logo";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { gsap, motionAllowed, registerGsap } from "@/lib/motion";
import { getAccess } from "@/lib/tokens";

const FIELD_NOTES = [
  { value: "7,761", label: "unions mapped" },
  { value: "16", label: "forecast days" },
  { value: "64", label: "districts covered" },
  { value: "2024", label: "FRG grounding" },
];

const METHOD = [
  {
    number: "01",
    title: "Tell us the field",
    body: "Share the land, location, season, water access, and working budget in ordinary language.",
    icon: MapPinned,
  },
  {
    number: "02",
    title: "Compare what fits",
    body: "AgriSense weighs weather, timing, crop needs, and cost before it narrows the choice.",
    icon: CloudSun,
  },
  {
    number: "03",
    title: "Carry the season",
    body: "Leave with dates, inputs, expected costs, and a plan you can revisit as conditions change.",
    icon: CalendarRange,
  },
  {
    number: "04",
    title: "Know the numbers",
    body: "Review input costs, expected revenue, and margin assumptions before committing the field.",
    icon: CircleDollarSign,
  },
  {
    number: "05",
    title: "Adjust with confidence",
    body: "Return when weather, prices, or field conditions shift and refine the plan with the new context.",
    icon: RefreshCcw,
  },
];

const CAPABILITIES = [
  {
    icon: MessageSquareText,
    label: "Field conversation",
    detail: "Ask, clarify, and revise without wrestling with a long form.",
  },
  {
    icon: BarChart3,
    label: "Cost ledger",
    detail: "See the assumptions behind revenue, input cost, and margin.",
  },
  {
    icon: CloudSun,
    label: "Weather context",
    detail: "Connect the plan to the conditions around your upazila.",
  },
  {
    icon: ShieldCheck,
    label: "Visible reasoning",
    detail: "Inspect the sources and tools used for the recommendation.",
  },
];

function PlanningSequence() {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      registerGsap();
      if (!motionAllowed() || !root.current) return;
      const media = gsap.matchMedia();
      media.add("(min-width: 1024px)", () => {
        const steps = gsap.utils.toArray<HTMLElement>("[data-method-step]");
        const line = root.current?.querySelector<SVGPathElement>("[data-route-line]");
        const lineLength = line?.getTotalLength() ?? 0;
        const timeline = gsap.timeline({
          scrollTrigger: {
            trigger: root.current,
            start: "top 18%",
            end: "+=950",
            scrub: 0.6,
            pin: "[data-method-map]",
          },
        });
        if (line) {
          gsap.set(line, {
            strokeDasharray: lineLength,
            strokeDashoffset: lineLength,
          });
          timeline.to(line, { strokeDashoffset: 0, duration: 1, ease: "none" });
        }
        timeline.fromTo(
          steps,
          { opacity: 0.38, x: 20 },
          { opacity: 1, x: 0, stagger: 0.3, duration: 0.75 },
          0,
        );
      });
      return () => media.revert();
    },
    { scope: root },
  );

  return (
    <div ref={root} className="mt-14 grid gap-10 lg:grid-cols-[0.78fr_1.22fr] lg:gap-20">
      <div data-method-map className="relative h-[390px] overflow-hidden border border-jute-300/60 bg-field-900 p-7 text-paper-50 lg:h-[520px]">
        <div className="absolute inset-0 opacity-20 atlas-grid" />
        <p className="relative font-mono text-[10px] uppercase tracking-[0.2em] text-jute-300">
          Seasonal route · one field
        </p>
        <svg viewBox="0 0 420 460" className="relative mt-8 h-[290px] w-full lg:h-[390px]" aria-hidden="true">
          <path
            data-route-line
            d="M44 58C118 5 176 124 239 86c87-52 135 45 96 112-38 65-160 14-168 98-7 81 128 50 145 117"
            fill="none"
            stroke="#D9C28F"
            strokeWidth="5"
            strokeLinecap="round"
          />
          <g fill="#F7F1DF" stroke="#17351B" strokeWidth="8">
            <circle cx="44" cy="58" r="13" />
            <circle cx="190" cy="94" r="13" />
            <circle cx="335" cy="198" r="13" />
            <circle cx="168" cy="296" r="13" />
            <circle cx="312" cy="413" r="13" />
          </g>
        </svg>
        <span className="absolute bottom-6 right-7 font-display text-7xl text-paper-50/10">বর্ষা</span>
      </div>

      <ol className="divide-y divide-jute-300/50">
        {METHOD.map((step) => (
          <li
            key={step.number}
            data-method-step
            className="grid gap-5 py-9 sm:grid-cols-[70px_1fr] sm:py-12"
          >
            <span className="font-mono text-sm text-clay-500">{step.number}</span>
            <div>
              <step.icon className="mb-5 text-field-600" size={25} strokeWidth={1.6} />
              <h3 className="font-display text-3xl tracking-[-0.035em] text-ink-900">
                {step.title}
              </h3>
              <p className="mt-3 max-w-lg leading-7 text-ink-500">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
export default function HomePage() {
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(Boolean(getAccess()));
  }, []);

  return (
    <main className="min-h-screen overflow-hidden bg-paper-50 text-ink-900">
      <header className="sticky top-0 z-40 border-b border-jute-300/45 bg-paper-50/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1380px] items-center justify-between px-5 py-3.5 sm:px-8">
          <Logo />
          <nav aria-label="Primary navigation" className="flex items-center gap-2">
            <Link
              href="/demo"
              className="hidden min-h-11 items-center px-3 text-sm font-semibold text-ink-700 transition hover:text-field-700 sm:inline-flex"
            >
              Field demo
            </Link>
            {authed ? (
              <Link href="/chat" className="atlas-button">
                <span className="sm:hidden">Open</span>
                <span className="hidden sm:inline">Open workspace</span>
                <ArrowUpRight size={16} />
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="min-h-11 px-3 py-3 text-sm font-semibold text-ink-700 transition hover:text-field-700"
                >
                  Log in
                </Link>
                <Link href="/register" className="atlas-button px-4 sm:px-5">
                  <span className="sm:hidden">Start</span>
                  <span className="hidden sm:inline">Start planning</span>
                  <ArrowUpRight size={16} />
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <section className="atlas-grid border-b border-jute-300/45">
        <div className="mx-auto grid min-h-[calc(100vh-70px)] max-w-[1380px] lg:grid-cols-[0.88fr_1.12fr]">
          <div className="flex items-center px-5 py-16 sm:px-8 lg:border-r lg:border-jute-300/45 lg:px-12 lg:py-24">
            <div className="max-w-2xl">
              <Reveal>
                <p className="atlas-kicker flex items-center gap-2">
                  <span className="h-px w-8 bg-clay-500" />
                  Crop planning for Bangladesh
                </p>
              </Reveal>
              <Reveal delay={70}>
                <h1 className="mt-7 font-display text-[clamp(3.2rem,6vw,6.8rem)] leading-[0.9] tracking-[-0.06em]">
                  Plan the season
                  <span className="mt-2 block italic text-field-600">before the soil</span>
                  pays for it.
                </h1>
              </Reveal>
              <Reveal delay={140}>
                <p className="mt-8 max-w-xl text-lg leading-8 text-ink-500">
                  Turn local conditions, a working budget, and one honest conversation into a
                  crop choice you can explain—and a season plan you can carry.
                </p>
              </Reveal>
              <Reveal delay={210}>
                <div className="mt-9 flex flex-wrap gap-3">
                  <Link href={authed ? "/chat" : "/register"} className="atlas-button">
                    Build a crop plan <ArrowRight size={17} />
                  </Link>
                  <Link href="/demo" className="atlas-button-secondary">
                    Explore the demo
                  </Link>
                </div>
              </Reveal>
              <Reveal delay={280}>
                <p className="mt-8 flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.17em] text-ink-500">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full border border-jute-300">
                    <Sprout size={13} className="text-field-600" />
                  </span>
                  Built for field decisions, not dashboards
                </p>
              </Reveal>
            </div>
          </div>

          <div className="relative min-h-[500px] border-t border-jute-300/45 lg:min-h-0 lg:border-t-0">
            <FieldAtlasScene />
          </div>
        </div>
      </section>

      <section aria-label="Field notes" className="border-b border-jute-300/45 bg-field-900 text-paper-50">
        <div className="mx-auto grid max-w-[1380px] grid-cols-2 divide-x divide-y divide-paper-50/15 sm:grid-cols-4 sm:divide-y-0">
          {FIELD_NOTES.map((note) => (
            <div key={note.label} className="px-5 py-7 sm:px-8">
              <p className="font-display text-4xl tracking-[-0.04em] text-jute-300">{note.value}</p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-paper-50/65">
                {note.label}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8 sm:py-32">
        <Reveal>
          <SectionHeading
            eyebrow="How the field becomes a plan"
            title="A decision trail you can follow from first question to harvest."
            description="The work stays legible: what you told us, what the conditions suggest, and how the final calendar was formed."
          />
        </Reveal>
        <PlanningSequence />
      </section>

      <section className="border-y border-jute-300/45 bg-paper-100">
        <div className="mx-auto grid max-w-[1380px] lg:grid-cols-[1.18fr_0.82fr]">
          <div className="relative min-h-[520px] overflow-hidden">
            <Image
              src="/images/paddy-reflection-bangladesh.jpg"
              alt="Green paddy fields reflected in water in rural Bangladesh"
              fill
              sizes="(min-width: 1024px) 60vw, 100vw"
              className="object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-field-900/45 via-transparent to-transparent" />
            <p className="absolute bottom-5 left-5 bg-paper-50/90 px-3 py-2 font-mono text-[9px] uppercase tracking-[0.15em] text-ink-700 backdrop-blur">
              Rural Bangladesh · Photo: A S M Jobaer
            </p>
          </div>
          <div className="flex items-center px-6 py-16 sm:px-12 lg:px-16">
            <Reveal>
              <p className="atlas-kicker">The reason for the ledger</p>
              <h2 className="mt-5 font-display text-4xl leading-[1.02] tracking-[-0.045em] sm:text-6xl">
                A field is never only an acreage.
              </h2>
              <p className="mt-6 text-lg leading-8 text-ink-500">
                Water, timing, cash, labour, and weather arrive together. AgriSense keeps those
                constraints in the same conversation so a promising crop does not become an
                impossible season.
              </p>
              <Link href="/demo" className="mt-8 inline-flex items-center gap-2 font-semibold text-field-700 underline decoration-jute-300 decoration-2 underline-offset-8">
                Walk through a sample season <ArrowUpRight size={17} />
              </Link>
            </Reveal>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1240px] px-5 py-24 sm:px-8 sm:py-32">
        <Reveal>
          <SectionHeading
            eyebrow="Inside the workspace"
            title="Four instruments. One agricultural decision."
            description="Each instrument earns its place by helping you understand, compare, or act."
          />
        </Reveal>
        <div className="mt-14 border-y border-jute-300/55">
          {CAPABILITIES.map((item, index) => (
            <Reveal key={item.label} delay={index * 55}>
              <div className="grid gap-5 border-b border-jute-300/55 py-7 last:border-b-0 sm:grid-cols-[64px_0.7fr_1.3fr] sm:items-center">
                <span className="font-mono text-xs text-clay-500">0{index + 1}</span>
                <h3 className="flex items-center gap-3 font-display text-2xl tracking-[-0.03em]">
                  <item.icon size={21} className="text-field-600" strokeWidth={1.7} />
                  {item.label}
                </h3>
                <p className="leading-7 text-ink-500">{item.detail}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="relative overflow-hidden bg-field-900 px-5 py-24 text-paper-50 sm:px-8 sm:py-32">
        <div className="absolute inset-0 opacity-[0.08] atlas-grid" />
        <div className="relative mx-auto grid max-w-[1240px] items-end gap-12 lg:grid-cols-[1fr_auto]">
          <Reveal>
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-jute-300">
              Your next season starts with one field note
            </p>
            <h2 className="mt-5 max-w-4xl font-display text-5xl leading-[0.95] tracking-[-0.055em] sm:text-7xl">
              Bring the land. Leave with the plan.
            </h2>
          </Reveal>
          <Reveal delay={90}>
            <Link href={authed ? "/chat" : "/register"} className="inline-flex min-h-14 items-center gap-3 rounded-full bg-paper-50 px-7 font-semibold text-field-900 transition hover:-translate-y-1 hover:bg-jute-100">
              Start planning <ArrowUpRight size={18} />
            </Link>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-jute-300/45 bg-paper-50">
        <div className="mx-auto flex max-w-[1380px] flex-col gap-5 px-5 py-8 text-sm text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span className="flex items-center gap-2.5">
            <LogoMark size={24} /> AgriSense · Delta Field Atlas
          </span>
          <span>Built for the IUT Bdapps Agentic AI Hackathon</span>
        </div>
      </footer>
    </main>
  );
}
