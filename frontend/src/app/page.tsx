"use client";

// Landing / home — the page users first hit ("/"). Marketing: hero with a light
// 2.5D scroll-parallax, how-it-works, BD farmer testimonials, and CTAs to sign up,
// log in, or try as a guest (no signup).

import { BarChart3, CloudSun, MessageSquareText, Sprout, Star } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Reveal } from "@/components/home/Reveal";
import { Logo, LogoMark } from "@/components/ui/Logo";
import { getAccess } from "@/lib/tokens";

const FEATURES = [
  {
    icon: MessageSquareText,
    title: "Just talk, in your own words",
    body: "Tell it your land, budget and season in plain language — it asks only for what's missing.",
  },
  {
    icon: CloudSun,
    title: "Real weather, real crop advice",
    body: "It calls live weather for your upazila and ranks the crops that actually fit your soil and season.",
  },
  {
    icon: BarChart3,
    title: "A costed, dated season plan",
    body: "Sowing to harvest, with fertilizer timing, irrigation, and a full cost → profit breakdown.",
  },
  {
    icon: Sprout,
    title: "Every number, explained",
    body: "See exactly which tool and which guide each recommendation came from — nothing invented.",
  },
];

interface Testimonial {
  name: string;
  where: string;
  story: string;
  stars: number;
  photo?: string; // drop a real BD farmer photo URL here; falls back to initials
}

const TESTIMONIALS: Testimonial[] = [
  {
    name: "Abdul Karim",
    where: "Tanore, Rajshahi",
    story:
      "I had 2 bigha of sandy land and no idea what to plant. It suggested wheat over potato because my canal water was limited — I followed the plan and cleared ৳15,800 profit this Rabi.",
    stars: 5,
    photo:
      "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Farmer_of_Rajshahi%2C_Bangladesh.JPG/250px-Farmer_of_Rajshahi%2C_Bangladesh.JPG",
  },
  {
    name: "Rehana Begum",
    where: "Mithapukur, Rangpur",
    story:
      "It warned me heavy rain was coming and told me to delay the urea by four days. That one message saved my fertilizer from washing away.",
    stars: 5,
    photo:
      "https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Smiling_farmer_in_Bangladesh.jpg/250px-Smiling_farmer_in_Bangladesh.jpg",
  },
  {
    name: "Jahangir Alam",
    where: "Bhola Sadar, Barisal",
    story:
      "A photo of my tomato leaf and it told me it was early blight and exactly which spray to use. My uncle in the next village now uses it too.",
    stars: 4,
    photo:
      "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/A_Village_Farmer_in_Bangladesh.jpg/250px-A_Village_Farmer_in_Bangladesh.jpg",
  },
  {
    name: "Mizanur Rahman",
    where: "Ullapara, Sirajganj",
    story:
      "At harvest it showed my cost, yield and profit in one screen — ৳27,000 revenue for ৳11,000 cost. I finally knew my numbers before I sold, not after.",
    stars: 5,
    photo:
      "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Farmer_bundling_harvested_rice_at_sunset_in_Bangladesh.jpg/250px-Farmer_bundling_harvested_rice_at_sunset_in_Bangladesh.jpg",
  },
  {
    name: "Shahida Khatun",
    where: "Shibganj, Chapainawabganj",
    story:
      "I just typed in Bangla what land I have and it asked only what it needed. No forms, no jargon — it felt like talking to a real krishi officer.",
    stars: 5,
    photo:
      "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Bangladeshi_farmer_and_the_magical_morning.jpg/250px-Bangladeshi_farmer_and_the_magical_morning.jpg",
  },
  {
    name: "Nurul Islam",
    where: "Fulbari, Dinajpur",
    story:
      "It gave me a dated calendar — sowing, urea timing, irrigation, harvest — and every recommendation said why. For the first time I planned the whole season on paper.",
    stars: 4,
    photo:
      "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/The_Bangladeshi_Farmer.jpg/250px-The_Bangladeshi_Farmer.jpg",
  },
];

function initials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function Avatar({ t }: { t: Testimonial }) {
  const [broken, setBroken] = useState(false);
  if (t.photo && !broken) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={t.photo}
        alt={t.name}
        onError={() => setBroken(true)}
        className="h-11 w-11 rounded-full object-cover"
      />
    );
  }
  return (
    <span className="flex h-11 w-11 items-center justify-center rounded-full bg-primary-100 font-display text-sm font-semibold text-primary-700">
      {initials(t.name)}
    </span>
  );
}

export default function HomePage() {
  const [authed, setAuthed] = useState(false);
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    setAuthed(!!getAccess());
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => setScrollY(window.scrollY));
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <main className="min-h-screen bg-background text-text-primary">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-border/70 bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <Logo />
          <nav className="flex items-center gap-2">
            {authed ? (
              <Link
                href="/chat"
                className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-primary-700"
              >
                Open app
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="rounded-lg px-3 py-2 text-sm font-medium text-text-primary transition hover:text-primary-700"
                >
                  Log in
                </Link>
                <Link
                  href="/register"
                  className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-primary-700"
                >
                  Sign up
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      {/* Hero with light 2.5D parallax */}
      <section className="relative overflow-hidden">
        {/* parallax decorative layers */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{ transform: `translateY(${scrollY * 0.15}px)` }}
        >
          <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary-100/60 blur-3xl" />
          <div className="absolute left-1/4 top-40 h-56 w-56 rounded-full bg-accent-100/50 blur-3xl" />
        </div>
        <div
          aria-hidden
          className="topo-bg pointer-events-none absolute inset-0 opacity-70"
          style={{ transform: `translateY(${scrollY * 0.05}px)` }}
        />

        {/* Floating sun */}
        <div
          aria-hidden
          className="pointer-events-none absolute right-[12%] top-16 h-24 w-24 animate-float rounded-full bg-accent-300 opacity-40 blur-md"
        />

        {/* Rolling fields (parallax) */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0"
          style={{ transform: `translateY(${scrollY * -0.06}px)` }}
        >
          <svg viewBox="0 0 1440 220" preserveAspectRatio="none" className="h-40 w-full sm:h-56">
            <path d="M0 140 Q360 90 720 130 T1440 120 V220 H0Z" fill="#DCF3E3" />
            <path d="M0 170 Q360 130 720 165 T1440 158 V220 H0Z" fill="#8AD5A4" opacity="0.75" />
            <path d="M0 196 Q360 166 720 190 T1440 184 V220 H0Z" fill="#22A55B" opacity="0.5" />
          </svg>
        </div>

        <div className="relative mx-auto max-w-4xl px-5 pb-16 pt-20 text-center sm:pt-28">
          <Reveal>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-primary-200 bg-primary-50 px-3 py-1 text-xs font-medium text-primary-700">
              <Sprout size={13} /> Agentic AI for smallholder farmers
            </span>
          </Reveal>
          <Reveal delay={80}>
            <h1 className="mx-auto mt-5 max-w-3xl font-display text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
              From an empty field to a{" "}
              <span className="text-primary-600">costed, weather-aware plan.</span>
            </h1>
          </Reveal>
          <Reveal delay={160}>
            <p className="mx-auto mt-5 max-w-xl text-lg text-text-muted">
              AgriSense talks to you like an agronomist — pulls real weather, ranks the right
              crops, and hands you a dated, costed season plan you can trust.
            </p>
          </Reveal>
          <Reveal delay={240}>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/register"
                className="rounded-xl bg-primary-600 px-6 py-3 font-medium text-white shadow-card transition hover:bg-primary-700"
              >
                Get started — it's free
              </Link>
              <Link
                href="/login"
                className="rounded-xl border border-border bg-surface px-6 py-3 font-medium text-text-primary transition hover:border-primary-300 hover:shadow-card"
              >
                Log in
              </Link>
            </div>
          </Reveal>
          <Reveal delay={320}>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 font-mono text-xs text-text-muted">
              {["Real weather", "84 crops ranked", "Grounded in FRG 2024", "No card needed"].map(
                (s) => (
                  <span key={s} className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary-500" />
                    {s}
                  </span>
                ),
              )}
            </div>
          </Reveal>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <Reveal>
          <h2 className="text-center font-display text-3xl font-semibold tracking-tight">
            How it works
          </h2>
        </Reveal>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={i * 90}>
              <div className="h-full rounded-2xl border border-border bg-surface p-5 shadow-card transition duration-300 hover:-translate-y-1.5 hover:border-primary-200 hover:shadow-lift">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-100 text-primary-600">
                  <f.icon size={20} />
                </span>
                <h3 className="mt-4 font-display text-base font-semibold">{f.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-text-muted">{f.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Testimonials */}
      <section className="bg-surface-muted py-16">
        <div className="mx-auto max-w-6xl px-5">
          <Reveal>
            <h2 className="text-center font-display text-3xl font-semibold tracking-tight">
              Farmers who planned with AgriSense
            </h2>
          </Reveal>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {TESTIMONIALS.map((t, i) => (
              <Reveal key={t.name} delay={i * 100}>
                <figure className="flex h-full flex-col rounded-2xl border border-border bg-surface p-6 shadow-card">
                  <div className="flex gap-0.5 text-accent-500">
                    {Array.from({ length: 5 }).map((_, s) => (
                      <Star
                        key={s}
                        size={15}
                        className={s < t.stars ? "fill-accent-500" : "text-border"}
                      />
                    ))}
                  </div>
                  <blockquote className="mt-3 flex-1 text-sm leading-relaxed text-text-primary">
                    “{t.story}”
                  </blockquote>
                  <figcaption className="mt-4 flex items-center gap-3 border-t border-border pt-4">
                    <Avatar t={t} />
                    <span>
                      <span className="block text-sm font-semibold">{t.name}</span>
                      <span className="block text-xs text-text-muted">{t.where}</span>
                    </span>
                  </figcaption>
                </figure>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="mx-auto max-w-4xl px-5 py-20 text-center">
        <Reveal>
          <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            Plan your next season with confidence.
          </h2>
          <p className="mx-auto mt-3 max-w-lg text-text-muted">
            Free to start. No card. Real weather and real agronomy from the first message.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Link
              href="/register"
              className="rounded-xl bg-primary-600 px-6 py-3 font-medium text-white shadow-card transition hover:bg-primary-700"
            >
              Create your account
            </Link>
            <Link
              href="/login"
              className="rounded-xl border border-border bg-surface px-6 py-3 font-medium text-text-primary transition hover:border-primary-300"
            >
              Log in
            </Link>
          </div>
        </Reveal>
      </section>

      <footer className="border-t border-border py-8 text-center text-sm text-text-muted">
        <span className="flex items-center justify-center gap-2">
          <LogoMark size={18} /> AgriSense — IUT Bdapps Agentic AI Hackathon
        </span>
      </footer>
    </main>
  );
}
