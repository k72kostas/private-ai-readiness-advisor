# Architecture

```mermaid
flowchart LR
 U[User] --> UI[Streamlit UI]
 UI --> V[Input validation]
 V --> E[Transparent rules engine]
 E --> R[Readiness report]
 R --> J[JSON export]
 R -->|optional| N[NVIDIA NIM compatible endpoint]
 N --> S[Executive summary]
 D[Approved documents] -->|future| X[Vector store]
 X --> N
```

## Design rules
- The deterministic assessment works without an LLM.
- The LLM narrative is optional and cannot change the score.
- Assumptions and limitations are visible.
- No confidential information is needed for the public demo.
