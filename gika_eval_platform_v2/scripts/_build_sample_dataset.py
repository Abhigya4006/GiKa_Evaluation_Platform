
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "sample_dataset"

DOCS = {
    "act": ("doc_eu_ai_act_full", "eu_ai_act_2024.pdf"),
    "gdpr": ("doc_gdpr", "gdpr_2016.pdf"),
    "guidelines": ("doc_ethics_guidelines", "trustworthy_ai_guidelines.pdf"),
    "annex": ("doc_ai_act_annex", "eu_ai_act_annexes.pdf"),
    "faq": ("doc_commission_faq", "commission_ai_act_faq.pdf"),
}


def doc(key, pages):
    did, fn = DOCS[key]
    return {"doc_id": did, "filename": fn, "page_numbers": pages}


def fact(fid, text, key):
    return {"fact_id": fid, "text": text, "doc_id": DOCS[key][0]}


def item(qid, query, answer, cats, diff, facts, docs, label="answerable", lang="en"):
    return {
        "query_id": qid,
        "query": query,
        "gt_answer": answer,
        "categories": cats,
        "difficulty": diff,
        "eval_label": label,
        "gt_supporting_facts": facts,
        "gt_documents": docs,
        "metadata": {"language": lang},
    }


ITEMS = [
    item("q_0001", "When was the EU AI Act officially published?", "12 July 2024",
         ["temporal", "lookup", "single-hop"], "easy",
         [fact("f_0001", "The EU AI Act was published in the Official Journal on 12 July 2024.", "act")],
         [doc("act", [3])]),

    item("q_0002", "When did the EU AI Act enter into force?", "1 August 2024",
         ["temporal", "lookup", "single-hop"], "easy",
         [fact("f_0002", "The AI Act entered into force on 1 August 2024, twenty days after publication.", "act")],
         [doc("act", [4])]),

    item("q_0003", "What are the four risk categories defined by the EU AI Act?",
         "Unacceptable, high, limited, and minimal risk",
         ["definition", "single-hop"], "medium",
         [fact("f_0003", "The AI Act classifies systems into unacceptable, high, limited and minimal risk.", "act")],
         [doc("act", [8])]),

    item("q_0004", "Which AI practices are prohibited under the EU AI Act?",
         "Practices such as social scoring by public authorities and manipulative subliminal techniques",
         ["definition", "entity-centric", "single-hop"], "medium",
         [fact("f_0004", "Prohibited practices include social scoring by public authorities.", "act"),
          fact("f_0005", "Prohibited practices include manipulative subliminal techniques causing harm.", "act")],
         [doc("act", [12, 13])]),

    item("q_0005", "What obligations apply to high-risk AI systems?",
         "Conformity assessment, risk management, data governance, and human oversight",
         ["multi-hop", "definition"], "hard",
         [fact("f_0006", "High-risk AI systems must undergo conformity assessments before market placement.", "act"),
          fact("f_0007", "High-risk systems require a risk management system throughout the lifecycle.", "act"),
          fact("f_0008", "High-risk systems require human oversight measures.", "act")],
         [doc("act", [22, 23, 24])]),

    item("q_0006", "What is the maximum administrative fine for prohibited AI practices?",
         "Up to 35 million euros or 7% of global annual turnover",
         ["numerical", "lookup", "single-hop"], "medium",
         [fact("f_0009", "Fines for prohibited practices can reach 35 million euros or 7% of worldwide annual turnover.", "act")],
         [doc("act", [40])]),

    item("q_0007", "Which body coordinates enforcement of the AI Act at EU level?",
         "The European AI Office",
         ["entity-centric", "lookup", "single-hop"], "easy",
         [fact("f_0010", "The European AI Office coordinates enforcement and supervision at Union level.", "act")],
         [doc("act", [45])]),

    item("q_0008", "How does the AI Act define a general-purpose AI model?",
         "An AI model with significant generality able to perform a wide range of tasks",
         ["definition", "single-hop"], "medium",
         [fact("f_0011", "A general-purpose AI model displays significant generality and can perform a wide range of distinct tasks.", "act")],
         [doc("act", [15])]),

    item("q_0009", "What transparency obligations apply to limited-risk AI like chatbots?",
         "Users must be informed they are interacting with an AI system",
         ["single-hop", "definition"], "medium",
         [fact("f_0012", "Providers of limited-risk systems must ensure users are informed they interact with an AI system.", "act")],
         [doc("act", [30])]),

    item("q_0010", "How does the EU AI Act relate to the GDPR on personal data?",
         "The AI Act complements GDPR; data protection rules continue to apply",
         ["multi-hop", "comparative"], "hard",
         [fact("f_0013", "The AI Act applies without prejudice to the GDPR, which continues to govern personal data processing.", "act"),
          fact("f_0014", "The GDPR establishes lawful bases for processing personal data.", "gdpr")],
         [doc("act", [6]), doc("gdpr", [10])]),

    item("q_0011", "What are the seven requirements for trustworthy AI in the EU ethics guidelines?",
         "Human agency, technical robustness, privacy, transparency, diversity, societal wellbeing, accountability",
         ["definition", "multi-hop"], "hard",
         [fact("f_0015", "Trustworthy AI guidelines list seven key requirements including human agency and oversight.", "guidelines"),
          fact("f_0016", "The requirements include technical robustness and safety.", "guidelines"),
          fact("f_0017", "The requirements include accountability.", "guidelines")],
         [doc("guidelines", [14, 15])]),

    item("q_0012", "Which annex lists high-risk AI use cases?",
         "Annex III",
         ["lookup", "single-hop", "temporal"], "easy",
         [fact("f_0018", "Annex III enumerates the high-risk AI use cases such as biometric identification.", "annex")],
         [doc("annex", [2])]),

    item("q_0013", "Is real-time remote biometric identification in public spaces banned?",
         "It is prohibited in principle for law enforcement, with narrow exceptions",
         ["single-hop", "definition"], "medium",
         [fact("f_0019", "Real-time remote biometric identification in publicly accessible spaces for law enforcement is prohibited, subject to narrow exceptions.", "act")],
         [doc("act", [13])]),

    item("q_0014", "What penalties apply for supplying incorrect information to authorities?",
         "Up to 7.5 million euros or 1% of global annual turnover",
         ["numerical", "lookup"], "medium",
         [fact("f_0020", "Supplying incorrect, incomplete or misleading information can lead to fines up to 7.5 million euros or 1% of annual turnover.", "act")],
         [doc("act", [41])]),

    item("q_0015", "What is a conformity assessment under the AI Act?",
         "A procedure demonstrating a high-risk system meets the Act's requirements",
         ["definition", "single-hop"], "medium",
         [fact("f_0021", "A conformity assessment is the process demonstrating that a high-risk AI system complies with the requirements of the Act.", "act")],
         [doc("act", [26])]),

    item("q_0016", "Which systems are considered minimal risk and largely unregulated?",
         "Systems such as spam filters and AI-enabled video games",
         ["definition", "entity-centric"], "medium",
         [fact("f_0022", "Minimal-risk systems, such as spam filters and AI in video games, face no additional obligations.", "act")],
         [doc("act", [31])]),

    item("q_0017", "Compare obligations for high-risk versus limited-risk AI systems.",
         "High-risk requires conformity assessment and oversight; limited-risk mainly requires transparency",
         ["comparative", "multi-hop"], "hard",
         [fact("f_0023", "High-risk systems require conformity assessment and human oversight.", "act"),
          fact("f_0024", "Limited-risk systems primarily face transparency obligations.", "act")],
         [doc("act", [23, 30])]),

    item("q_0018", "When do obligations for general-purpose AI models start applying?",
         "12 months after entry into force (August 2025)",
         ["temporal", "numerical"], "hard",
         [fact("f_0025", "Obligations for general-purpose AI models apply from 12 months after entry into force.", "act")],
         [doc("act", [48])]),

    item("q_0019", "What is the role of notified bodies?",
         "Independent bodies that assess conformity of certain high-risk systems",
         ["entity-centric", "definition"], "medium",
         [fact("f_0026", "Notified bodies are independent conformity assessment bodies designated by Member States.", "act")],
         [doc("act", [27])]),

    item("q_0020", "Does the AI Act apply to providers established outside the EU?",
         "Yes, if their AI system's output is used in the EU",
         ["single-hop", "definition"], "medium",
         [fact("f_0027", "The AI Act applies to providers outside the EU where the output of the system is used within the Union.", "act")],
         [doc("act", [5])]),

    # ---- Intentionally harder / failure-prone cases below ----

    item("q_0021", "What documentation must providers of high-risk systems keep?",
         "Technical documentation and automatically generated logs",
         ["multi-hop", "definition"], "hard",
         [fact("f_0028", "Providers must draw up technical documentation before the system is placed on the market.", "act"),
          fact("f_0029", "High-risk systems must enable automatic recording of logs over their lifetime.", "act")],
         [doc("act", [24, 25])]),

    item("q_0022", "How is 'serious incident' defined under the AI Act?",
         "An incident leading to death, serious harm to health, or serious disruption of critical infrastructure",
         ["definition", "single-hop"], "hard",
         [fact("f_0030", "A serious incident is defined as an event leading to death or serious damage to health, property, or critical infrastructure.", "act")],
         [doc("act", [37])]),

    item("q_0023", "What is the grace period before most AI Act rules fully apply?",
         "24 months after entry into force (August 2026)",
         ["temporal", "numerical"], "hard",
         [fact("f_0031", "Most provisions of the AI Act apply 24 months after entry into force.", "act")],
         [doc("act", [49])]),

    item("q_0024", "Which regulator handles GDPR complaints about automated decisions?",
         "National data protection authorities",
         ["entity-centric", "multi-hop"], "hard",
         [fact("f_0032", "National data protection authorities enforce the GDPR, including rules on automated individual decision-making.", "gdpr")],
         [doc("gdpr", [22])]),

    item("q_0025", "What are codes of practice used for under the AI Act?",
         "To detail compliance for general-purpose AI providers before harmonised standards exist",
         ["definition", "multi-hop"], "hard",
         [fact("f_0033", "Codes of practice help general-purpose AI providers demonstrate compliance pending harmonised standards.", "act")],
         [doc("act", [47])]),

    item("q_0026", "How many pages is the consolidated EU AI Act text?",
         "Approximately 144 pages in the Official Journal",
         ["numerical", "lookup"], "hard",
         [fact("f_0034", "The consolidated AI Act text spans roughly 144 pages in the Official Journal.", "faq")],
         [doc("faq", [1])]),

    item("q_0027", "Does the AI Act regulate open-source AI models?",
         "Free and open-source models are partly exempt unless they are high-risk or GPAI with systemic risk",
         ["multi-hop", "comparative"], "hard",
         [fact("f_0035", "Free and open-source AI components benefit from exemptions unless they are high-risk or systemic-risk GPAI.", "act")],
         [doc("act", [17])]),

    item("q_0028", "What threshold defines general-purpose AI with systemic risk?",
         "Training compute above 10^25 floating-point operations",
         ["numerical", "temporal", "lookup"], "hard",
         [fact("f_0036", "A general-purpose AI model is presumed to pose systemic risk when training compute exceeds 10^25 FLOP.", "act")],
         [doc("act", [16])]),

    item("q_0029", "Who bears obligations when a system is substantially modified?",
         "The party making the substantial modification is treated as a new provider",
         ["multi-hop", "entity-centric"], "hard",
         [fact("f_0037", "A party that substantially modifies a high-risk system assumes the obligations of a provider.", "act")],
         [doc("act", [21])]),

    item("q_0030", "What is the sandbox mechanism in the AI Act?",
         "Regulatory sandboxes let providers test innovative AI under supervision",
         ["definition", "single-hop"], "medium",
         [fact("f_0038", "AI regulatory sandboxes provide a controlled environment to develop and test AI systems under regulatory supervision.", "act")],
         [doc("act", [35])]),

    # A deliberately unanswerable / out-of-scope query.
    item("q_0031", "What is the EU AI Act's position on faster-than-light communication?",
         "Not addressed by the AI Act",
         ["single-hop", "lookup"], "hard",
         [],  # no GT facts -> tests answerability / no-retrieval handling
         [], label="unanswerable"),

    item("q_0032", "What must deployers of emotion recognition systems do?",
         "Inform natural persons exposed to the system",
         ["single-hop", "definition"], "medium",
         [fact("f_0039", "Deployers of emotion recognition systems must inform the natural persons exposed to them.", "act")],
         [doc("act", [32])]),
]

DATASET = {
    "dataset_id": "eu_ai_act_bench",
    "name": "EU AI Act Benchmark",
    "version": "1.0.0",
    "domain": "eu_regulations",
    "source": "internal-curated",
    "metric_config": {"recall_at_k": [1, 3, 5, 10], "em_normalize": True},
    "leaderboard": [
        {"system_name": "BaselineRAG", "metric": "f1", "value": 0.71},
        {"system_name": "BaselineRAG", "metric": "exact_match", "value": 0.58},
        {"system_name": "BaselineRAG", "metric": "recall", "value": 0.74},
        {"system_name": "BaselineRAG", "metric": "document_recall", "value": 0.69},
        {"system_name": "GraphRAG-v2", "metric": "f1", "value": 0.80},
        {"system_name": "GraphRAG-v2", "metric": "exact_match", "value": 0.66},
    ],
    "items": ITEMS,
}

LEADERBOARD = {"dataset_id": "eu_ai_act_bench", "entries": DATASET["leaderboard"]}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "dataset.json").write_text(json.dumps(DATASET, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "leaderboard.json").write_text(json.dumps(LEADERBOARD, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(ITEMS)} queries to {OUT_DIR/'dataset.json'}")


if __name__ == "__main__":
    main()
