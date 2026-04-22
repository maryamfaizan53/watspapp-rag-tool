import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";

// ─── Animated counter hook ────────────────────────────────────────────────────
function useCounter(target: number, duration = 2000, active = false) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!active) return;
    let start = 0;
    const step = target / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= target) { setCount(target); clearInterval(timer); }
      else setCount(Math.floor(start));
    }, 16);
    return () => clearInterval(timer);
  }, [active, target, duration]);
  return count;
}

// ─── Intersection observer hook ───────────────────────────────────────────────
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

// ─── Chat message type ────────────────────────────────────────────────────────
interface ChatMsg { sender: "user" | "bot"; text: string; }

const CHAT_SEQUENCE: ChatMsg[] = [
  { sender: "user", text: "What is KSE-100 index today?" },
  { sender: "bot", text: "The KSE-100 is Pakistan's benchmark stock index tracking the top 100 companies by market capitalisation. It's the primary gauge of PSX performance. 📈" },
  { sender: "user", text: "How do I open an account?" },
  { sender: "bot", text: "Opening a CDC account is easy! Steps: 1) Choose a SECP-licensed broker 2) Submit CNIC + bank details 3) Fund your account. Takes 2–3 working days. Want the full guide? ✅" },
];

// ─── Animated Chat Mockup ─────────────────────────────────────────────────────
function ChatMockup() {
  const [visibleCount, setVisibleCount] = useState(0);
  const [showTyping, setShowTyping] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      for (let i = 0; i < CHAT_SEQUENCE.length; i++) {
        if (cancelled) return;
        // show typing indicator before bot messages
        if (CHAT_SEQUENCE[i].sender === "bot") {
          setShowTyping(true);
          await new Promise(r => setTimeout(r, 1200));
          if (cancelled) return;
          setShowTyping(false);
        }
        setVisibleCount(i + 1);
        await new Promise(r => setTimeout(r, 1600));
      }
      // restart loop after a pause
      await new Promise(r => setTimeout(r, 3000));
      if (!cancelled) { setVisibleCount(0); setShowTyping(false); run(); }
    }
    run();
    return () => { cancelled = true; };
  }, []);

  return (
    <div style={{
      background: "rgba(255,255,255,0.04)",
      backdropFilter: "blur(20px)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 24,
      overflow: "hidden",
      boxShadow: "0 32px 80px rgba(0,0,0,0.5)",
      animation: "slideInRight 0.8s ease 0.2s both",
    }}>
      {/* Header */}
      <div style={{
        background: "#075e54",
        padding: "16px 20px",
        display: "flex", alignItems: "center", gap: 12,
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: "50%",
          background: "linear-gradient(135deg, #25d366, #128c7e)",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20,
        }}>🤖</div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, color: "#fff" }}>PSX Investment Bot</div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.65)" }}>● online</div>
        </div>
      </div>

      {/* Messages */}
      <div style={{
        background: "#0a1628",
        padding: "20px 16px",
        minHeight: 260,
        display: "flex", flexDirection: "column", gap: 10,
      }}>
        {CHAT_SEQUENCE.slice(0, visibleCount).map((m, i) => (
          <div key={i} style={{
            display: "flex",
            justifyContent: m.sender === "user" ? "flex-end" : "flex-start",
            animation: "fadeInUp 0.4s ease both",
          }}>
            <div style={{
              maxWidth: "82%",
              padding: "9px 13px",
              borderRadius: m.sender === "user" ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
              background: m.sender === "user" ? "#056162" : "#1f2c34",
              fontSize: 13, color: "#e9edef", lineHeight: 1.55,
            }}>
              {m.text}
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {showTyping && (
          <div style={{ display: "flex", justifyContent: "flex-start", animation: "fadeIn 0.3s ease" }}>
            <div style={{
              padding: "10px 14px", borderRadius: "14px 14px 14px 2px",
              background: "#1f2c34",
              display: "flex", alignItems: "center", gap: 4,
            }}>
              {[0, 1, 2].map(d => (
                <span key={d} style={{
                  width: 7, height: 7, borderRadius: "50%",
                  background: "#8696a0", display: "inline-block",
                  animation: `typingDot 1.2s ease-in-out ${d * 0.2}s infinite`,
                }} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Input bar */}
      <div style={{
        background: "#0a1628",
        padding: "10px 16px 16px",
        borderTop: "1px solid rgba(255,255,255,0.05)",
      }}>
        <div style={{
          background: "#1f2c34", borderRadius: 24,
          padding: "10px 16px", display: "flex", alignItems: "center", gap: 10,
        }}>
          <span style={{ flex: 1, fontSize: 13, color: "#8696a0" }}>Type a message…</span>
          <span style={{ color: "#25d366" }}>🎤</span>
        </div>
      </div>
    </div>
  );
}

// ─── Data ─────────────────────────────────────────────────────────────────────
const FEATURES = [
  { icon: "🌙", title: "24/7 Availability", desc: "Never miss a client query. Your bot works around the clock, even on holidays." },
  { icon: "🇵🇰", title: "Urdu & English", desc: "Bilingual AI that auto-detects language and responds naturally in both." },
  { icon: "🔒", title: "Private & Secure", desc: "Your data, your bot, your clients. Isolated knowledge bases per tenant." },
  { icon: "📊", title: "Analytics Dashboard", desc: "Track usage, message counts, and conversation quality in real-time." },
  { icon: "⚡", title: "Instant Responses", desc: "Sub-3 second answers. Your clients never wait, no matter the volume." },
  { icon: "📄", title: "Document Trained", desc: "Answers only from your uploaded content. No hallucinations." },
];

const PLANS = [
  {
    icon: "⭐", name: "Starter", price: "Rs 10,000", setup: "Rs 25,000", period: "/mo",
    highlight: false, color: "#06b6d4",
    features: ["1 Channel (WhatsApp OR Telegram)", "Up to 500 messages/month", "5 documents", "Email support", "Admin dashboard"],
  },
  {
    icon: "🚀", name: "Growth", price: "Rs 18,000", setup: "Rs 35,000", period: "/mo",
    highlight: true, color: "#8b5cf6",
    features: ["WhatsApp + Telegram", "Up to 2,000 messages/month", "20 documents", "Priority support", "Analytics dashboard", "Custom branding"],
  },
  {
    icon: "💼", name: "Enterprise", price: "Custom", setup: "", period: "",
    highlight: false, color: "#f59e0b",
    features: ["Unlimited channels", "Unlimited messages", "Unlimited documents", "Dedicated support", "Custom branding", "SLA guarantee"],
  },
];

const FAQS = [
  { q: "What if the bot gives wrong information?", a: "The bot is grounded exclusively in your uploaded documents. If it can't find an answer, it says so gracefully rather than guessing. You stay in full control of what it knows." },
  { q: "Is my data secure?", a: "All data is encrypted in transit and at rest. Each client's knowledge base is completely isolated — we never use your documents to train shared models." },
  { q: "How long does setup take?", a: "Most clients are live within 48 hours. We handle all technical configuration — you just upload your documents and share the bot link with your clients." },
  { q: "Can clients use it without technical knowledge?", a: "Absolutely. Your clients just open WhatsApp or Telegram and type their question — exactly like any normal chat. No apps to install, no logins required." },
  { q: "What happens after the free pilot?", a: "After your 30-day pilot, you choose a plan that fits your message volume. There's no lock-in and you can cancel or upgrade anytime." },
];

// ─── Main Component ───────────────────────────────────────────────────────────
export default function Landing() {
  const [scrolled, setScrolled] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const demoRef = useRef<HTMLDivElement>(null);

  const statsSection = useInView(0.2);
  const howSection = useInView(0.1);
  const featSection = useInView(0.1);
  const pricingSection = useInView(0.05);
  const faqSection = useInView(0.1);
  const ctaSection = useInView(0.2);

  const c500 = useCounter(500, 2000, statsSection.inView);
  const cUptime = useCounter(999, 2000, statsSection.inView);
  const _c3 = useCounter(3, 1500, statsSection.inView); void _c3;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div style={{ background: "#080d1a", color: "#f1f5f9", overflowX: "hidden" }}>

      {/* ── NAVBAR ── */}
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 48px", height: 70,
        background: scrolled ? "rgba(8,13,26,0.85)" : "transparent",
        backdropFilter: scrolled ? "blur(20px)" : "none",
        borderBottom: scrolled ? "1px solid rgba(255,255,255,0.07)" : "none",
        transition: "all 0.4s ease",
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
          }}>🤖</div>
          <span style={{ fontWeight: 800, fontSize: 20, letterSpacing: "-0.5px" }}>
            Bot<span style={{
              background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
            }}>IQ</span>
          </span>
        </div>

        {/* Nav links */}
        <div style={{ display: "flex", alignItems: "center", gap: 36 }}>
          {[["Features", "#features"], ["How it Works", "#how"], ["Pricing", "#pricing"], ["Contact", "#cta"]].map(([label, href]) => (
            <a key={label} href={href} style={{ color: "#94a3b8", fontSize: 14, fontWeight: 500, transition: "color 0.2s" }}
              onMouseEnter={e => (e.currentTarget.style.color = "#f1f5f9")}
              onMouseLeave={e => (e.currentTarget.style.color = "#94a3b8")}>
              {label}
            </a>
          ))}
        </div>

        {/* CTA */}
        <Link to="/login">
          <button className="btn-primary" style={{ padding: "10px 24px", fontSize: 14 }}>
            Get Started →
          </button>
        </Link>
      </nav>

      {/* ── HERO ── */}
      <section style={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        padding: "100px 48px 60px", position: "relative", overflow: "hidden",
      }}>
        {/* Background glows */}
        <div style={{
          position: "absolute", top: "8%", left: "2%", width: 700, height: 700,
          background: "radial-gradient(circle, rgba(6,182,212,0.1) 0%, transparent 65%)",
          borderRadius: "50%", pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", bottom: "5%", right: "5%", width: 550, height: 550,
          background: "radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 65%)",
          borderRadius: "50%", pointerEvents: "none",
        }} />

        <div style={{
          maxWidth: 1200, margin: "0 auto", width: "100%",
          display: "flex", alignItems: "center", gap: 80,
        }}>
          {/* Left text */}
          <div style={{ flex: 1, animation: "slideInLeft 0.8s ease both" }}>
            {/* Badge */}
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              background: "rgba(6,182,212,0.08)", border: "1px solid rgba(6,182,212,0.2)",
              borderRadius: 100, padding: "6px 16px", marginBottom: 28,
            }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981", display: "inline-block" }} />
              <span style={{ fontSize: 13, color: "#06b6d4", fontWeight: 500 }}>AI-Powered for PSX Investors</span>
            </div>

            <h1 style={{
              fontSize: "clamp(36px, 5vw, 62px)", fontWeight: 800,
              lineHeight: 1.08, letterSpacing: "-2px", marginBottom: 12,
            }}>
              Your Clients Ask Questions<br />at Midnight.
            </h1>
            <h1 style={{
              fontSize: "clamp(36px, 5vw, 62px)", fontWeight: 800,
              lineHeight: 1.08, letterSpacing: "-2px", marginBottom: 28,
              background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
            }}>
              Who's Answering Them?
            </h1>

            <p style={{ fontSize: 18, color: "#94a3b8", lineHeight: 1.7, marginBottom: 40, maxWidth: 500 }}>
              AI-powered WhatsApp &amp; Telegram bots trained on your documents. Live in 48 hours.
            </p>

            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              <button className="btn-primary" style={{ fontSize: 16 }}
                onClick={() => demoRef.current?.scrollIntoView({ behavior: "smooth" })}>
                💬 Book a Live Demo
              </button>
              <button className="btn-secondary" style={{ fontSize: 16 }}
                onClick={() => demoRef.current?.scrollIntoView({ behavior: "smooth" })}>
                Watch it Work →
              </button>
            </div>

            <p style={{ marginTop: 24, fontSize: 13, color: "#475569" }}>
              No credit card required · Live in 48 hours · Cancel anytime
            </p>
          </div>

          {/* Right: chat mockup */}
          <div style={{ flex: "0 0 380px" }}>
            <ChatMockup />
          </div>
        </div>
      </section>

      {/* ── STATS BAR ── */}
      <div ref={statsSection.ref} style={{ padding: "0 48px 80px" }}>
        <div style={{
          maxWidth: 1200, margin: "0 auto",
          display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: 20,
          animation: statsSection.inView ? "fadeInUp 0.7s ease both" : "none",
        }}>
          {[
            { value: `${c500}+`, label: "Queries Answered Daily", icon: "💬", color: "#06b6d4" },
            { value: "48hrs", label: "Go-Live Guarantee", icon: "🚀", color: "#8b5cf6", static: true },
            { value: `${(cUptime / 10).toFixed(1)}%`, label: "Uptime SLA", icon: "⚡", color: "#10b981" },
          ].map((s, i) => (
            <div key={i} style={{
              textAlign: "center", padding: "40px 32px",
              borderRight: i < 2 ? "1px solid rgba(255,255,255,0.07)" : "none",
            }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>{s.icon}</div>
              <div style={{ fontSize: 42, fontWeight: 800, color: s.color, marginBottom: 8, letterSpacing: "-1.5px" }}>
                {s.value}
              </div>
              <div style={{ fontSize: 14, color: "#94a3b8", fontWeight: 500 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── HOW IT WORKS ── */}
      <section id="how" style={{ padding: "80px 48px", maxWidth: 1200, margin: "0 auto" }}>
        <div ref={howSection.ref} style={{
          textAlign: "center", marginBottom: 60,
          animation: howSection.inView ? "fadeInUp 0.7s ease both" : "none",
          opacity: howSection.inView ? 1 : 0,
        }}>
          <div style={{ fontSize: 12, color: "#06b6d4", fontWeight: 700, letterSpacing: "2.5px", textTransform: "uppercase", marginBottom: 14 }}>Simple Setup</div>
          <h2 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-1.5px" }}>How It Works</h2>
          <p style={{ color: "#94a3b8", marginTop: 12, fontSize: 17, maxWidth: 500, margin: "12px auto 0" }}>Three steps from signup to your first bot reply</p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 28 }}>
          {[
            { step: "01", icon: "📄", title: "Share Your Documents", desc: "Upload PDFs, Word files, FAQs, prospectuses — anything your clients ask about. Our system ingests and indexes everything." },
            { step: "02", icon: "🤖", title: "We Train Your Bot", desc: "The AI builds a semantic knowledge base from your docs. It learns context, not just keywords. Ready in under 24 hours." },
            { step: "03", icon: "📱", title: "Share with Clients", desc: "Connect your WhatsApp number or Telegram bot token. Send the link to clients. Done. First reply in seconds." },
          ].map((s, i) => (
            <div key={i} className="glass-card" style={{
              padding: 36, position: "relative", overflow: "hidden",
              animation: howSection.inView ? `fadeInUp 0.7s ease ${i * 0.15}s both` : "none",
              opacity: howSection.inView ? 1 : 0,
              transition: "transform 0.3s, border-color 0.3s",
            }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.transform = "translateY(-4px)";
                (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(6,182,212,0.25)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
                (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.07)";
              }}
            >
              {/* Big step number watermark */}
              <div style={{
                position: "absolute", top: -16, right: -4,
                fontSize: 90, fontWeight: 900, color: "rgba(255,255,255,0.025)", lineHeight: 1, userSelect: "none",
              }}>{s.step}</div>

              {/* Number badge */}
              <div style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                width: 28, height: 28, borderRadius: 8,
                background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
                fontSize: 13, fontWeight: 800, color: "#fff", marginBottom: 20,
              }}>{i + 1}</div>

              <div style={{
                width: 52, height: 52, borderRadius: 14,
                background: "linear-gradient(135deg, rgba(6,182,212,0.12), rgba(139,92,246,0.12))",
                border: "1px solid rgba(6,182,212,0.15)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 26, marginBottom: 20,
              }}>{s.icon}</div>

              <h3 style={{ fontSize: 19, fontWeight: 700, marginBottom: 12 }}>{s.title}</h3>
              <p style={{ color: "#94a3b8", lineHeight: 1.7, fontSize: 14 }}>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── FEATURES GRID ── */}
      <section id="features" style={{ padding: "80px 48px", maxWidth: 1200, margin: "0 auto" }}>
        <div ref={featSection.ref} style={{
          textAlign: "center", marginBottom: 60,
          animation: featSection.inView ? "fadeInUp 0.7s ease both" : "none",
          opacity: featSection.inView ? 1 : 0,
        }}>
          <div style={{ fontSize: 12, color: "#8b5cf6", fontWeight: 700, letterSpacing: "2.5px", textTransform: "uppercase", marginBottom: 14 }}>Why BotIQ</div>
          <h2 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-1.5px" }}>Everything You Need</h2>
          <p style={{ color: "#94a3b8", marginTop: 12, fontSize: 17, maxWidth: 500, margin: "12px auto 0" }}>Built specifically for PSX brokers and investment firms</p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24 }}>
          {FEATURES.map((f, i) => (
            <div key={i} className="glass-card" style={{
              padding: 28, cursor: "default", transition: "all 0.3s ease",
              animation: featSection.inView ? `fadeInUp 0.6s ease ${i * 0.1}s both` : "none",
              opacity: featSection.inView ? 1 : 0,
            }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.06)";
                (e.currentTarget as HTMLDivElement).style.transform = "translateY(-4px)";
                (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(6,182,212,0.25)";
                (e.currentTarget as HTMLDivElement).style.boxShadow = "0 12px 40px rgba(0,0,0,0.3), 0 0 0 1px rgba(6,182,212,0.1)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.03)";
                (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
                (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.07)";
                (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
              }}
            >
              <div style={{
                width: 50, height: 50, borderRadius: 13, fontSize: 24,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: "linear-gradient(135deg, rgba(6,182,212,0.12), rgba(139,92,246,0.12))",
                border: "1px solid rgba(255,255,255,0.06)", marginBottom: 18,
              }}>{f.icon}</div>
              <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 10 }}>{f.title}</h3>
              <p style={{ color: "#94a3b8", fontSize: 14, lineHeight: 1.65 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── PRICING ── */}
      <section id="pricing" style={{ padding: "80px 48px" }}>
        <div ref={pricingSection.ref} style={{
          textAlign: "center", marginBottom: 60, maxWidth: 1200, margin: "0 auto 60px",
          animation: pricingSection.inView ? "fadeInUp 0.7s ease both" : "none",
          opacity: pricingSection.inView ? 1 : 0,
        }}>
          <div style={{ fontSize: 12, color: "#f59e0b", fontWeight: 700, letterSpacing: "2.5px", textTransform: "uppercase", marginBottom: 14 }}>Pricing</div>
          <h2 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-1.5px" }}>Simple, Transparent Plans</h2>
          <p style={{ color: "#94a3b8", marginTop: 12, fontSize: 17 }}>No hidden fees. Cancel anytime.</p>
        </div>

        <div style={{
          maxWidth: 1100, margin: "0 auto",
          display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24, alignItems: "center",
        }}>
          {PLANS.map((p, i) => (
            <div key={i} style={{
              borderRadius: 22, padding: "40px 32px", position: "relative", overflow: "hidden",
              background: p.highlight
                ? "linear-gradient(135deg, rgba(6,182,212,0.08), rgba(139,92,246,0.12))"
                : "rgba(255,255,255,0.03)",
              border: p.highlight ? "1px solid rgba(139,92,246,0.5)" : "1px solid rgba(255,255,255,0.07)",
              transform: p.highlight ? "scale(1.04)" : "scale(1)",
              boxShadow: p.highlight ? "0 0 60px rgba(139,92,246,0.12), 0 4px 24px rgba(0,0,0,0.4)" : "0 4px 24px rgba(0,0,0,0.2)",
              animation: pricingSection.inView ? `fadeInUp 0.6s ease ${i * 0.15}s both` : "none",
              opacity: pricingSection.inView ? 1 : 0,
              transition: "transform 0.3s",
            }}>
              {p.highlight && (
                <div style={{
                  position: "absolute", top: 18, right: 18,
                  background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
                  color: "#fff", fontSize: 10, fontWeight: 800, letterSpacing: "1.5px",
                  padding: "5px 12px", borderRadius: 100, textTransform: "uppercase",
                }}>Most Popular</div>
              )}

              <div style={{ fontSize: 30, marginBottom: 10 }}>{p.icon}</div>
              <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4, color: p.color }}>{p.name}</h3>
              {p.setup && <div style={{ fontSize: 12, color: "#475569", marginBottom: 16 }}>Setup: {p.setup}</div>}

              <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 28 }}>
                <span style={{ fontSize: 36, fontWeight: 800 }}>{p.price}</span>
                {p.period && <span style={{ fontSize: 14, color: "#94a3b8" }}>{p.period}</span>}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 13, marginBottom: 32 }}>
                {p.features.map((f, j) => (
                  <div key={j} style={{ display: "flex", alignItems: "flex-start", gap: 10, fontSize: 14, color: "#94a3b8" }}>
                    <span style={{ color: "#10b981", fontSize: 14, flexShrink: 0, marginTop: 1 }}>✅</span>
                    {f}
                  </div>
                ))}
              </div>

              <Link to="/login">
                <button style={{
                  width: "100%", padding: "14px 0", borderRadius: 12, border: "none",
                  background: p.highlight ? "linear-gradient(135deg, #06b6d4, #8b5cf6)" : "rgba(255,255,255,0.08)",
                  color: "#f1f5f9", fontWeight: 600, fontSize: 15, cursor: "pointer",
                  transition: "all 0.3s",
                  boxShadow: p.highlight ? "0 4px 24px rgba(6,182,212,0.3)" : "none",
                }}
                  onMouseEnter={e => (e.currentTarget.style.transform = "translateY(-2px)")}
                  onMouseLeave={e => (e.currentTarget.style.transform = "translateY(0)")}
                >
                  {i === 2 ? "Contact Sales →" : "Get Started →"}
                </button>
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ ── */}
      <section style={{ padding: "80px 48px", maxWidth: 860, margin: "0 auto" }}>
        <div ref={faqSection.ref} style={{
          textAlign: "center", marginBottom: 56,
          animation: faqSection.inView ? "fadeInUp 0.7s ease both" : "none",
          opacity: faqSection.inView ? 1 : 0,
        }}>
          <div style={{ fontSize: 12, color: "#06b6d4", fontWeight: 700, letterSpacing: "2.5px", textTransform: "uppercase", marginBottom: 14 }}>FAQ</div>
          <h2 style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-1.5px" }}>Common Questions</h2>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {FAQS.map((faq, i) => (
            <div key={i} style={{
              background: "rgba(255,255,255,0.03)",
              border: `1px solid ${openFaq === i ? "rgba(6,182,212,0.3)" : "rgba(255,255,255,0.07)"}`,
              borderRadius: 14, overflow: "hidden",
              transition: "border-color 0.25s",
              animation: faqSection.inView ? `fadeInUp 0.5s ease ${i * 0.08}s both` : "none",
              opacity: faqSection.inView ? 1 : 0,
            }}>
              <button onClick={() => setOpenFaq(openFaq === i ? null : i)} style={{
                width: "100%", padding: "20px 24px",
                background: "none", border: "none",
                display: "flex", alignItems: "center", justifyContent: "space-between",
                color: "#f1f5f9", fontSize: 16, fontWeight: 600, textAlign: "left", cursor: "pointer",
              }}>
                {faq.q}
                <span style={{
                  fontSize: 22, color: "#06b6d4", lineHeight: 1,
                  transition: "transform 0.3s",
                  transform: openFaq === i ? "rotate(45deg)" : "rotate(0deg)",
                  display: "inline-block",
                }}>+</span>
              </button>
              {openFaq === i && (
                <div style={{
                  padding: "0 24px 22px", color: "#94a3b8", lineHeight: 1.75, fontSize: 15,
                  animation: "fadeInUp 0.3s ease both",
                }}>
                  {faq.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── FINAL CTA ── */}
      <section id="cta" ref={ctaSection.ref} style={{
        padding: "100px 48px", textAlign: "center", position: "relative", overflow: "hidden",
        background: "linear-gradient(135deg, rgba(6,182,212,0.06), rgba(139,92,246,0.08))",
        borderTop: "1px solid rgba(255,255,255,0.05)",
      }}>
        <div style={{
          position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
          width: 700, height: 400,
          background: "radial-gradient(ellipse, rgba(139,92,246,0.15) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />
        <div style={{
          position: "relative", maxWidth: 640, margin: "0 auto",
          animation: ctaSection.inView ? "fadeInUp 0.8s ease both" : "none",
          opacity: ctaSection.inView ? 1 : 0,
        }}>
          <h2 style={{ fontSize: 48, fontWeight: 800, letterSpacing: "-1.5px", marginBottom: 20 }}>
            Ready to Transform Your<br />
            <span style={{
              background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
            }}>Client Experience?</span>
          </h2>
          <p style={{ color: "#94a3b8", fontSize: 18, lineHeight: 1.65, marginBottom: 48 }}>
            Join forward-thinking Pakistani financial firms already using AI to answer thousands of client questions automatically, every day.
          </p>
          <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
            <Link to="/login">
              <button className="btn-primary animate-pulse-glow" style={{ fontSize: 17 }}>
                🚀 Start Your Free 30-Day Pilot
              </button>
            </Link>
            <a href="https://wa.me/923001234567" target="_blank" rel="noopener noreferrer">
              <button className="btn-secondary" style={{ fontSize: 17 }}>
                💬 Chat on WhatsApp
              </button>
            </a>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer style={{
        padding: "36px 48px",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        background: "#080d1a",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        flexWrap: "wrap", gap: 24,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8,
            background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15,
          }}>🤖</div>
          <span style={{ fontWeight: 800, fontSize: 17 }}>
            Bot<span style={{
              background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
            }}>IQ</span>
          </span>
          <span style={{ color: "#475569", fontSize: 13, marginLeft: 8 }}>AI chatbots for Pakistan's financial sector</span>
        </div>

        <div style={{ display: "flex", gap: 28 }}>
          {["Features", "Pricing", "Contact", "Privacy", "Terms"].map(l => (
            <a key={l} href={`#${l.toLowerCase()}`} style={{ color: "#475569", fontSize: 13, transition: "color 0.2s" }}
              onMouseEnter={e => (e.currentTarget.style.color = "#94a3b8")}
              onMouseLeave={e => (e.currentTarget.style.color = "#475569")}>
              {l}
            </a>
          ))}
        </div>

        <div style={{ color: "#475569", fontSize: 13 }}>
          © {new Date().getFullYear()} BotIQ. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
