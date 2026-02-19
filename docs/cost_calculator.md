# 💰 Superactive Cost Calculator (The "Owner" Economics)

This document breaks down exactly what you will pay when your $200 Google Cloud credits expire.

**The Short Answer:**
You will pay **~$0.04 per minute**.
Competitors (Retell/Bland) charge **$0.15 - $0.20 per minute**.
**You save ~80%.**

---

## 1. The Breakdown (Per Minute of Conversation)

Assumptions:
*   Conversation is 50% User / 50% AI.
*   Speaking rate: ~150 words per minute.
*   Voice: Google **Chirp HD** (Premium Geneartive) — *The most expensive option.*

| Component | Provider | Unit Price | Usage/Min | Cost/Min |
| :--- | :--- | :--- | :--- | :--- |
| **Telephony** | Twilio | $0.013 / min | 1 min | **$0.0130** |
| **Hearing (STT)** | Google Cloud | $0.006 / 15s | 1 min | **$0.0240*** |
| **Brain (LLM)** | Gemini 2.0 Flash | $0.15 / 1M tokens | ~300 tokens | **$0.0001** |
| **Voice (TTS)** | Google Chirp HD | $30.00 / 1M chars | ~375 chars | **$0.0113** |
| | | | | |
| **TOTAL** | | | | **$0.0484** |

*\*Note on STT: Using "Standard" models ($0.006/15sec = $0.024/min) is the default. You can switch to OpenAI Whisper (Host yourself) to drop this to $0.00.*

### Cheaper Alternative (Standard Quality)
If you switch TTS to "Standard WaveNet" (Robot-like):
*   TTS Cost: $0.001 / min
*   **Total Cost: ~$0.038 / min**

---

## 2. Monthly Usage Examples

### Scenario A: The "Pilot" (One Dentist Office)
*   **Volume:** 500 calls / month.
*   **Avg Duration:** 3 minutes.
*   **Total Minutes:** 1,500 mins.

| Platform | Rate | Monthly Bill | Margin (if charging $500) |
| :--- | :--- | :--- | :--- |
| **Wrapper (Retell)** | $0.20/min | $300.00 | $200 Profit |
| **Superactive (You)** | $0.05/min | **$75.00** | **$425 Profit** |

### Scenario B: The "Agency" (10 Clients)
*   **Volume:** 15,000 mins / month.

| Platform | Rate | Monthly Bill |
| :--- | :--- | :--- |
| **Wrapper (Retell)** | $0.15/min (Bulk) | $2,250.00 |
| **Superactive (You)** | $0.05/min | **$750.00** |
| | | |
| **YOUR SAVINGS** | | **$1,500 / month** |

---

## 3. How to optimize further?

1.  **Switch STT to Deepgram Nova-2:**
    *   Google: $0.024/min
    *   Deepgram: $0.0043/min
    *   *Saves $0.02/min immediately.*

2.  **Self-Host Whisper (STT):**
    *   Cost: Fixed GPU cost (~$30/mo).
    *   Per-minute: $0.00.

3.  **Switch LLM to Llama 3 (Groq):**
    *   Gemini is already extremely cheap, so this is negligible savings.

---

## 4. The "Hidden" Business Costs (Overhead)

Beyond the per-minute costs, here are the fixed and transactional costs of running the business.

### A. Infrastructure (Fixed Monthly)
*   **VPS Hosting:** ~$10 - $20 / month (DigitalOcean/AWS/Hetzner) to run the Python code 24/7.
*   **Cloudflare:** $0 - $20 / month.
    *   **Tunnels:** Free.
    *   **Pro Plan (Optional):** $20/mo for WAF if you get attacked.
*   **Database:** $0 - $25 / month (Supabase/Neon free tiers are generous, scale to paid later).
*   **Phone Numbers:** $1.15 / month per number (Twilio).
    *   If you have 10 clients, that's **$11.50/mo**.

### B. Transactional & Legal
*   **Payment Processing (Stripe):** 2.9% + $30¢ per transaction.
    *   On a $500 retainer, Stripe takes **~$14.80**.
*   **Taxes:** Varies by jurisdiction.
    *   Check if you need to collect Sales Tax/VAT on digital services in your client's state.
*   **LLC/Incorporation:** ~$300 - $800 / year (State fees + Registered Agent).

### Total Business Overhead Estimate (Monthly)
*   **Fixed:** ~$30.00 / month (Hosting + DB + 10 Numbers)
*   **Transactional:** ~3% of Revenue.

## Conclusion
Even with overhead, your margins remain massive compared to reselling via wrappers.
*   **Wrapper Margin:** ~20-30%
*   **Owner Margin:** ~70-80%
