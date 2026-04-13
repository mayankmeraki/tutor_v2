"""Generate Euler Capabilities PDF document."""
import os
from fpdf import FPDF

class EulerPDF(FPDF):
    def setup_fonts(self):
        font_dir = "/System/Library/Fonts/Supplemental/"
        self.add_font("DejaVu", "", os.path.join(font_dir, "Arial Unicode.ttf"), uni=True)
        self.add_font("DejaVu", "B", os.path.join(font_dir, "Arial Unicode.ttf"), uni=True)
        self.add_font("DejaVu", "I", os.path.join(font_dir, "Arial Unicode.ttf"), uni=True)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("DejaVu", "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 6, "Euler AI Tutor - Capability Document", align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title):
        self.set_font("DejaVu", "B", 13)
        self.set_text_color(22, 78, 99)
        self.cell(0, 9, title)
        self.ln(5)
        self.set_draw_color(52, 211, 153)
        self.set_line_width(0.6)
        self.line(self.get_x(), self.get_y(), self.get_x() + 45, self.get_y())
        self.ln(6)

    def sub_title(self, title):
        self.set_font("DejaVu", "B", 10.5)
        self.set_text_color(55, 65, 81)
        self.cell(0, 7, title)
        self.ln(6)

    def body_text(self, text):
        self.set_font("DejaVu", "", 9.5)
        self.set_text_color(55, 65, 81)
        self.multi_cell(0, 5.2, text)
        self.ln(2)

    def bullet(self, text, indent=10):
        x = self.get_x()
        self.set_font("DejaVu", "", 9.5)
        self.set_text_color(55, 65, 81)
        self.set_x(x + indent)
        self.cell(4, 5.2, "\u2022")
        self.multi_cell(0, 5.2, text)
        self.ln(1)

    def bullet_bold_lead(self, bold_part, rest, indent=10):
        x = self.get_x()
        self.set_x(x + indent)
        self.set_font("DejaVu", "", 9.5)
        self.set_text_color(55, 65, 81)
        self.cell(4, 5.2, "\u2022")
        self.set_font("DejaVu", "B", 9.5)
        self.set_text_color(30, 41, 59)
        w = self.get_string_width(bold_part + " ") + 1
        self.cell(w, 5.2, bold_part + " ")
        self.set_font("DejaVu", "", 9.5)
        self.set_text_color(55, 65, 81)
        self.multi_cell(0, 5.2, rest)
        self.ln(1)


pdf = EulerPDF()
pdf.setup_fonts()
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)

# ── Cover page ──
pdf.add_page()
pdf.ln(50)
pdf.set_font("DejaVu", "B", 32)
pdf.set_text_color(15, 23, 42)
pdf.cell(0, 14, "Euler", align="C")
pdf.ln(14)
pdf.set_font("DejaVu", "", 14)
pdf.set_text_color(100, 116, 139)
pdf.cell(0, 8, "AI Tutor Capability Document", align="C")
pdf.ln(30)
pdf.set_font("DejaVu", "", 10)
pdf.set_text_color(100, 116, 139)
pdf.cell(0, 6, "An AI tutor that teaches live on a board, speaks, adapts,", align="C")
pdf.ln(6)
pdf.cell(0, 6, "and assesses understanding in real time.", align="C")
pdf.ln(40)
pdf.set_font("DejaVu", "", 9)
pdf.set_text_color(160, 160, 160)
pdf.cell(0, 6, "Capacity AI  |  April 2026  |  Confidential", align="C")

# ── Page 2: Teaching Modalities ──
pdf.add_page()
pdf.section_title("1. Live Teaching Modalities")
pdf.body_text("Euler teaches through multiple simultaneous modalities, orchestrated in real time by the AI. Every session is a live, adaptive experience — not pre-recorded content.")

pdf.sub_title("Board Drawing (Chalk Engine)")
pdf.bullet_bold_lead("Live visual board:", "The tutor draws on a digital board in real time — equations, diagrams, step-by-step derivations, comparisons, and annotated visuals. Content appears progressively as the tutor speaks, like a real classroom board.")
pdf.bullet_bold_lead("SVG primitives:", "Lines, arrows, rectangles, circles, arcs, dots, dashed lines, curved arrows — all positioned on an 800x500 coordinate canvas for precise diagram construction.")
pdf.bullet_bold_lead("Rich content types:", "LaTeX equations, comparison tables, step-by-step blocks, callouts, annotations, code blocks, Mermaid diagrams, column layouts, and numbered lists.")

pdf.sub_title("Voice Teaching")
pdf.bullet_bold_lead("Text-to-speech:", "The tutor speaks with natural voice, synchronized with board drawing. Voice scenes control pacing — the board draws in sync with narration beats.")
pdf.bullet_bold_lead("Pacing control:", "Voice beats with configurable pauses ensure the student can follow along. The tutor pauses at key moments for emphasis.")

pdf.sub_title("Animations & Simulations")
pdf.bullet_bold_lead("Custom p5.js animations:", "The AI generates bespoke animations per concept — e.g., a spring-mass system, electromagnetic wave propagation, projectile trajectories. These are written on-the-fly, not from a fixed library.")
pdf.bullet_bold_lead("3D visualizations:", "Three.js scenes with orbit controls for spatial concepts — crystal structures, vector fields, molecular geometries.")
pdf.bullet_bold_lead("Interactive widgets:", "Custom HTML/CSS/JS widgets with live parameter controls (sliders, inputs) that report state back to the tutor. The tutor can react to student interactions.")
pdf.bullet_bold_lead("Pre-built simulations:", "For courses with simulation libraries, the tutor can launch, control parameters, and discuss results of interactive simulations.")

pdf.sub_title("AI-Generated Interactives")
pdf.bullet_bold_lead("Visual generation agent:", "A background agent produces full self-contained HTML interactives — explorable explanations, interactive diagrams, parameter spaces — delivered mid-session.")

pdf.sub_title("Images & Media")
pdf.bullet_bold_lead("Web image search:", "The tutor searches for and displays relevant images (diagrams, photographs, micrographs) directly on the board.")
pdf.bullet_bold_lead("Video clips:", "For course-based sessions, the tutor can cue specific segments of lecture videos at precise timestamps.")

# ── Page 3: Student Adaptation ──
pdf.add_page()
pdf.section_title("2. Student Adaptation")
pdf.body_text("Euler maintains a live student model that updates every turn. The tutor's behavior, depth, pacing, and style continuously adapt based on observed evidence.")

pdf.sub_title("Live Student Profiling")
pdf.bullet_bold_lead("Per-concept tracking:", "Each concept is tracked at a Bloom's taxonomy level (Remember through Create), with evidence-based observations and teaching implications.")
pdf.bullet_bold_lead("Cross-cutting style profile:", "Tracks whether the student is a visual learner, prefers formal/informal language, needs more examples, or responds to Socratic questioning.")
pdf.bullet_bold_lead("Revisit tracking:", "If a student revisits a concept, the tutor notes prior mastery level and adjusts — no re-teaching what's already understood.")

pdf.sub_title("Adaptive Behaviors")
pdf.bullet_bold_lead("Early signal detection:", "Identifies fast learners (skip basics, go deeper), slow learners (more scaffolding, simpler examples), pattern-matchers (test with variants), anxious students (more encouragement), and over-confident students (probe harder).")
pdf.bullet_bold_lead("Depth calibration:", "Teaches one Bloom's level above current mastery. If a student is at 'Understand', the tutor pushes toward 'Apply' — never stays static.")
pdf.bullet_bold_lead("Disengagement response:", "If the student seems disengaged, the tutor reduces questioning load, introduces more visuals/animations, and offers to explain before asking.")
pdf.bullet_bold_lead("Socratic by default:", "The tutor defaults to guided questioning but adapts — some students respond better to direct explanation followed by verification.")

pdf.sub_title("Evidence Model")
pdf.bullet_bold_lead("7-level evidence scale:", "From L1 (no evidence) to L7 (transfer mastery). The tutor requires evidence before advancing — never assumes understanding from silence.")
pdf.bullet_bold_lead("Verify before advancing:", "Each concept must be verified through the student's own words, problem-solving, or application before the tutor moves on.")

# ── Page 4: Learning Modes ──
pdf.add_page()
pdf.section_title("3. Learning Modes")
pdf.body_text("Euler supports multiple learning scenarios, each with specialized behavior and tool access.")

pdf.sub_title("Free Exploration")
pdf.bullet_bold_lead("Curiosity-driven:", "The student asks anything — the tutor builds a teaching path on the fly, grounds content via web search, and teaches with full board + voice.")
pdf.bullet_bold_lead("No prerequisites:", "Works without any course material. The tutor sources content from the web and its own knowledge.")

pdf.sub_title("Course-Based Learning")
pdf.bullet_bold_lead("Structured curriculum:", "Follows an uploaded course syllabus — lessons, modules, lecture content. The tutor teaches from the professor's material, not generic content.")
pdf.bullet_bold_lead("Content grounding:", "Every explanation references actual course material via content tools (content_map, content_read, content_search). The tutor cites specific sections.")
pdf.bullet_bold_lead("Step types:", "Each topic in the plan follows a pedagogical arc — Orient, Present, Check, Deepen, Consolidate.")

pdf.sub_title("Video Follow-Along")
pdf.bullet_bold_lead("Pause and ask:", "Student watches a lecture video. At any point they pause and ask a question — the tutor answers using the transcript context (~60s window around the pause point).")
pdf.bullet_bold_lead("Transcript-grounded:", "Answers cite what the professor said, enriched with key points, formulas, and concepts from that section.")
pdf.bullet_bold_lead("Resume control:", "The tutor can resume or seek the video programmatically after answering.")

pdf.sub_title("Bring Your Own Materials (BYO)")
pdf.bullet_bold_lead("Upload anything:", "PDFs, notes, lecture slides, problem sets, images, audio, video. Materials are processed and indexed for the tutor to reference.")
pdf.bullet_bold_lead("Teach from your content:", "The tutor reads and teaches directly from uploaded materials — explaining homework problems, summarizing notes, or drilling key concepts from the student's own resources.")

pdf.sub_title("Exam Preparation")
pdf.bullet_bold_lead("Full exam coverage:", "Diagnose knowledge gaps, patch weak areas, drill with problem variants, verify mastery.")
pdf.bullet_bold_lead("Single topic deep-dive:", "Focus on one concept until the breakdown point is found and resolved.")

# ── Page 5: Assessment ──
pdf.add_page()
pdf.section_title("4. Assessment System")
pdf.body_text("Assessment is woven into the teaching flow — not bolted on. The tutor transitions between teaching and assessing seamlessly.")

pdf.sub_title("Inline Assessment (During Teaching)")
pdf.bullet("Multiple-choice questions rendered on the board with immediate feedback")
pdf.bullet("Free-text responses where the student explains in their own words")
pdf.bullet("Confidence checks — student rates their own confidence, tutor calibrates")
pdf.bullet("Spot-the-error — student identifies mistakes in presented work")
pdf.bullet("Teach-back — student explains a concept back to the tutor")
pdf.bullet("Fill-in-the-blank for equations and key terms")
pdf.bullet("Agree/disagree with reasoning prompts")

pdf.sub_title("Formal Assessment Agent")
pdf.bullet_bold_lead("Dedicated agent:", "A separate assessment agent runs with its own message history and specialized tools. It focuses purely on evaluation — no teaching during assessment.")
pdf.bullet_bold_lead("Structured brief:", "The teaching tutor hands off a detailed brief — section, concepts, student profile, plan context, and content grounding — so the assessor asks targeted questions.")
pdf.bullet_bold_lead("Format mixing:", "The assessment agent is required to vary question types (MCQ, freetext, spot-error, numerical) to avoid pattern-gaming.")
pdf.bullet_bold_lead("Score-based routing:", "After assessment, scores route the student: <40% returns to teaching, 40-69% continues with reinforcement, >=70% advances to the next section.")

pdf.sub_title("Knowledge State Persistence")
pdf.bullet("Concept mastery persists across sessions — returning students pick up where they left off")
pdf.bullet("Assessment results update the student model's Bloom's level per concept")

# ── Page 6: Planning & Orchestration ──
pdf.add_page()
pdf.section_title("5. Planning & Agent Orchestration")
pdf.body_text("Euler uses a multi-agent architecture. Background agents handle planning, content enrichment, and visual generation while the main tutor teaches.")

pdf.sub_title("Planning Agent")
pdf.bullet_bold_lead("Auto-triggered:", "After ~4 conversational turns (when enough student context exists), a planning agent spawns automatically in the background.")
pdf.bullet_bold_lead("Tool-equipped:", "The planner uses content search, web search, and knowledge tools to ground the plan in real material — not just generic topic lists.")
pdf.bullet_bold_lead("Structured output:", "Produces a JSON plan with sections, topics, step types (orient/present/check/deepen/consolidate), and content summaries.")
pdf.bullet_bold_lead("Mutable:", "The tutor can modify the plan mid-session — insert prerequisite topics, skip ahead, end detours — based on student needs.")

pdf.sub_title("Enrichment Agent")
pdf.bullet_bold_lead("Shadow enrichment:", "Runs in the background every ~5 turns, searching for supplementary content, examples, and analogies that the tutor can weave into the session.")

pdf.sub_title("Visual Generation Agent")
pdf.bullet_bold_lead("On-demand interactives:", "When the tutor needs a complex visualization, it spawns a visual generation agent that produces a self-contained HTML interactive, delivered asynchronously.")

pdf.sub_title("Delegation")
pdf.bullet_bold_lead("Sub-tutor delegation:", "The main tutor can delegate a bounded teaching task (e.g., a prerequisite review) to a sub-agent with its own turn budget, then resume control.")

# ── Page 7: Technical Architecture ──
pdf.add_page()
pdf.section_title("6. Session & Conversation Architecture")

pdf.sub_title("Session Lifecycle")
pdf.bullet_bold_lead("Triage phase:", "Initial turns assess what the student knows and wants. The tutor uses this to calibrate the session's starting point and depth.")
pdf.bullet_bold_lead("Planning phase:", "Background planning agent builds a personalized lesson plan grounded in course material or web content.")
pdf.bullet_bold_lead("Teaching phase:", "The core loop — tutor teaches, assesses inline, adapts, and advances through the plan.")
pdf.bullet_bold_lead("Assessment phase:", "Formal assessment at section boundaries to verify mastery before advancing.")

pdf.sub_title("Real-Time Streaming")
pdf.bullet_bold_lead("SSE + WebSocket:", "Teaching content streams to the client in real time — board draws appear progressively, voice plays in sync, animations render as they're generated.")
pdf.bullet_bold_lead("Eager parsing:", "The frontend parses AI output tags as they stream in (not waiting for completion), enabling real-time board updates mid-generation.")

pdf.sub_title("Tool Ecosystem")
pdf.body_text("The tutor has access to 20+ tools spanning content retrieval, web search, image search, simulation control, student model updates, plan management, assessment handoff, board interaction, and agent orchestration.")

pdf.sub_title("Board Interaction")
pdf.bullet_bold_lead("Student drawing:", "Students can draw on the board (pen tool). The tutor can snapshot the board (including student annotations) and reason about what the student drew.")

# ── Page 8: What This Means ──
pdf.add_page()
pdf.section_title("7. What Makes This Different")
pdf.body_text("Most AI education tools are chatbots that answer questions. Euler is a teaching system that conducts live lessons.")

pdf.ln(4)
pdf.sub_title("Teaches, doesn't just answer")
pdf.body_text("Euler follows a pedagogical arc — it orients the student, presents concepts visually, checks understanding, deepens with harder problems, and consolidates. It doesn't dump information.")

pdf.sub_title("Multi-modal by default")
pdf.body_text("Every concept is taught with a combination of board visuals, voice narration, equations, diagrams, and animations. The tutor chooses the right modality for each concept.")

pdf.sub_title("Adapts in real time")
pdf.body_text("The student model updates every turn. A fast learner gets deeper content and harder problems. A struggling student gets more scaffolding, simpler examples, and visual aids. This isn't a one-size-fits-all experience.")

pdf.sub_title("Grounded in real content")
pdf.body_text("For course-based learning, the tutor teaches from the actual curriculum — professor's lectures, textbook sections, problem sets. For free exploration, it grounds in web search results. It never fabricates without sourcing.")

pdf.sub_title("Assessment is native")
pdf.body_text("Understanding is verified, not assumed. The tutor checks comprehension inline, runs formal assessments at section boundaries, and routes students based on demonstrated mastery.")

pdf.sub_title("Works with your materials")
pdf.body_text("Upload any study material — PDFs, notes, videos, problem sets — and the tutor teaches from it. This makes Euler useful for any curriculum, any institution, any student.")

# ── Save ──
out = "/Users/admin/Downloads/work/capacity/mockup/Euler_Capabilities.pdf"
pdf.output(out)
print(f"PDF saved to {out}")
