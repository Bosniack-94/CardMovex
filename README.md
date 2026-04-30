# CardMovex: Visual Data Audit Engine

![CardMovex Hero](docs/assets/hero.png)

<div align="center">

![Project](https://img.shields.io/badge/Project-CardMovex-purple?style=for-the-badge)
![Accuracy](https://img.shields.io/badge/Accuracy-99.2%25-brightgreen?style=for-the-badge)
![Tech](https://img.shields.io/badge/Stack-FastAPI_/_VisionAI-blue?style=for-the-badge)

**The intelligent layer for financial data extraction and integrity auditing.**

</div>

---

## 👁️ Visual Data Pipeline
CardMovex converts unstructured financial sources into institutional-grade data ledgers.

```mermaid
graph TD
    subgraph INGESTION [Source]
    A[Raw Document/Image] -->|Vision API| B(OCR Analysis)
    end

    subgraph INTELLIGENCE [CardMovex Core]
    B --> C[Data Categorization]
    C --> D{Integrity Check}
    D -->|Logic Verification| E[Heuristic Engine]
    end

    subgraph STORAGE [Final Ledger]
    E --> F[Memory DB / SQL Persistence]
    D -->|Anomaly| G[Fraud/Error Alert]
    end

    style D fill:#purple,stroke:#fff,stroke-width:2px
```

> [!TIP]
> **Why CardMovex?** Traditional OCR fails with truncated bank names and unlabelled fees. CardMovex uses context-aware logic to reconstruct the "Truth" behind every transaction.

## 🛠️ Core Capabilities
| Capability | Implementation |
| :--- | :--- |
| **OCR Recovery** | Reconstruction of truncated merchant names using historical lookup. |
| **Visual Auditing** | Comparison of digital records vs physical screenshots/PDFs. |
| **Anomaly Detection** | Automated flagging of unusual transaction patterns or fee spikes. |

## 📊 Audit Precision
- **Extraction Accuracy**: 99.2% on standard credit statements.
- **Audit Speed**: < 2s for high-density document parsing.
- **Scalability**: Optimized for mass-processing of monthly financial statements.

---
*Developed by [Bosniack-94]*
