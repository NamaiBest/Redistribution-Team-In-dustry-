# FreshRetailNet-50K: Business-Oriented Perishable Retail Analytics & Optimization Workflow

This `artifacts/` directory houses our **business-first analytical pipeline** built on the **FreshRetailNet-50K** dataset (`901,800` store-product-day records across `19` columns, deterministic 20% sample) and aligned with the **IIT Madras B.S. Business Analytics** and **Industry 4.0** curricula.

Instead of jumping straight into black-box ML/routing pipelines, our workflow follows a structured, hypothesis-driven consulting and operations research sequence:

[1. Problem Statement] ──▶ [2. Systemic EDA] ──▶ [3. Research Questions (RQ1–RQ4)]
──▶ [4. Empirical Inferences] ──▶ [5. Integrated Optimization Model] ──▶ [6. Report & Proctor Slides]


---

## 1. Core Problem Statement

Perishable and fresh-retail SKUs experience sharp intraday demand peaks, calendar/weather swings, and steep promotional elasticity, yet frequent daytime stockouts (`stock_hour6_22_cnt`) censor observed sales (`sale_amount`) and distort naive demand forecasts.

**Objective:** Estimate true uncensored demand, price/promotion elasticity, and calendar/weather drivers from historical store-SKU data, and translate those empirical parameters into **stockout-aware replenishment, pricing, and redistribution/allocation decisions** under operational capacity and shelf-presence constraints.

---

## 2. Step-by-Step Project Workflow

### Stage 1 — Problem Definition & Scope Framing *(Completed)*
* **Dataset:** FreshRetailNet-50K (`sale_amount`, 24-hour `hours_sale` & `hours_stock_status` arrays, `stock_hour6_22_cnt`, `discount`, `activity_flag`, `holiday_flag`, weather covariates, and store/product/management hierarchies).
* **Scope & Constraints:** `sale_amount` and `hours_sale` are globally normalised volume metrics (not currency revenue or physical spoilage weights), `discount` is a price multiplier ($1.0 =$ full price), and basket-level receipts are replaced by store-day category co-occurrence.

### Stage 2 — Systemic Exploratory Data Analysis (EDA) *(Completed)*
* Audited schema integrity, missingness (`0` nulls across all 19 columns), univariate distributions, skewness, and zero-inflation.
* Verified structural relationships across promotional flags (`activity_flag`), discount tiers, holiday indicators, and store/category hierarchies before running inferential models.

### Stage 3 — Empirical Research Questions (RQ1–RQ4) *(Completed in Notebook)*

| RQ | Analytical Focus | BA & Industry 4.0 Methods Used | Key Empirical Inferences |
| :--- | :--- | :--- | :--- |
| **RQ1** | **Intraday Demand Curves & Latent Demand Censoring** | 24-hour array decomposition, in-stock conditional profiling, baseline demand quartile stratification (`Q1`–`Q4`) | Demand peaks at **09:00** (`0.1054`) with a secondary afternoon wave at **15:00–16:00**, while stockouts accumulate through the day to **41.94%** at **22:00** (daytime avg **19.89%**). In-stock vs. observed sales reveal up to a **34.84%** daytime censoring gap, and multi-hour stockouts sharply depress daily sales across every demand tier. |
| **RQ2** | **Promotional Discounts, Campaigns & Price Elasticity** | Linear vs. Constant-Elasticity (Log-Log) OLS regression, interaction terms, VIF diagnostics | Deep discounts ($\le 0.70$) lift mean daily sales nearly **2.7×** (`2.1758` vs. `0.8083` full price). Demand is price-elastic (**$\varepsilon = -1.26$**, $p < 0.0001$). Once discount depth is controlled for, `activity_flag` adds no independent lift (`97.8%` of campaigns already carry discounts; $\text{VIF} \approx 2.44$), and stockouts attenuate discount gains. |
| **RQ3** | **Calendar, Weather & Operational Unit Efficiency** | Contingency table & Chi-square ($\chi^2$) test, Multiple Linear Regression (MLR), Input-Oriented CCR DEA (`linprog`) | Adding calendar and weather predictors lifts MLR $R^2$ to **0.2493**: weekends (`+0.1753`) and holidays (`+0.1059`) raise demand, while stockouts (`-0.0337/hr`) and wind (`-0.0666`) reduce it. CCR-DEA identifies `management_group_id` **2** and **6** on the efficiency frontier ($\theta = 1.00$), while groups **1** ($\theta = 0.58$) and **4** ($\theta = 0.60$) show significant operational slack. |
| **RQ4** | **Category Co-Movement & Stockout-Aware Allocation** | Apriori association rule mining (`support`, `confidence`, `lift`), Linear Programming (`linprog`) capacity allocation | **Category 8** acts as a central traffic anchor, co-occurring with Categories **21, 10, 18, 20, and 4** at lifts up to **1.30**. Under a 20% supply shortfall, naive sales-share allocation understocks fast-moving, stockout-prone categories (`21`, `29`), whereas stockout-aware LP prioritizes high-demand categories (while highlighting the need for a minimum shelf-presence constraint $x_i \ge x_{\min}$). |

---

## 4. What We Need Next (Integration & Technical Modelling)

Now that **EDA and RQ1–RQ4 are complete**, the repository's technical modelling layer should consume the empirical outputs above rather than operating on uncalibrated assumptions:

1. **Uncensored Demand & Safety-Stock / Newsvendor Calibration (`W5_L5.2`, `W6_L6.2`):**
   * Use the RQ1 daytime stockout censoring adjustment and RQ3 calendar/weather regression multipliers to reconstruct **uncensored expected demand ($\hat{D}_{i,t}$)** and demand variance ($\hat{\sigma}_{i,t}$) per store/category.
2. **Joint Pricing, Replenishment & Redistribution Optimization (`L25`–`L28`, `W7_L7.1`–`L7.5`, `W9_L9.5`):**
   * **Objective:** Maximize expected fulfilled value / margin across stores and categories (or minimize stockout + spoilage/holding mismatch).
   * **Decision Variables:** Replenishment / inter-store redistribution quantities ($x_{i,s}$) and promotional discount tier selection ($d_{i,s}$), governed by the RQ2 elasticity curve ($\varepsilon = -1.26$).
   * **Constraints:**
     * Total supply / warehouse / vehicle capacity limits ($\sum x_{i,s} \le C$).
     * Minimum shelf-presence / anchor-category floor ($x_{i,s} \ge x_{\min}$, preserving Apriori traffic drivers like Category `8`).
     * Store-level efficiency / stockout risk caps informed by RQ3 DEA benchmarks.
3. **Final Report & Proctor Presentation Deck:**
   * Compile the end-to-end narrative: *Business Problem $\rightarrow$ EDA Findings $\rightarrow$ RQ1–RQ4 Evidence $\rightarrow$ Integrated Optimization Model Results $\rightarrow$ Constraints & Managerial Recommendations*.