import json

def build_roast_prompt(
    promptType: str,
    roastIntensity: str = "sarcastic",
    outcomeType: str = "neutral",
    userLocale: str = "en-US",
    currency: str = "USD",
    portfolioData: dict = None,
    benchmarkData: dict = None,
    behavioralSignals: dict = None,
    achievements: list = None,
    fireProgress: dict = None,
    constraints: dict = None,
    commentaryMode: str = "OPENING_CHECK",
    recentRoasts: list = None,
    messageAngle: str = None,
    scenarioKey: str = None
) -> dict:
    """
    Builds a structured prompt for AI-generated portfolio commentary.
    """
    
    # ── 1. Base System Prompt (Static) ─────────────────────────────────────────
    system_prompt = (
        "You are the Roastfolio AI Roast Engine.\n\n"
        "Your job is to generate funny but useful portfolio commentary.\n\n"
        "Safety rules:\n"
        "- Do not provide direct financial advice.\n"
        "- Do not tell the user to buy, sell, hold, short, leverage, or go all-in on any asset.\n"
        "- Do not predict future market movements with certainty.\n"
        "- You may describe historical performance and risks.\n"
        "- You may suggest areas to review, not specific trades.\n"
        "- Do not insult protected traits or personal identity.\n"
        "- Avoid slurs, hate, self-harm references, mental health insults, or extreme degradation.\n"
        "- Humor should target investing behavior, not the user's identity.\n\n"
        "Novelty rules:\n"
        "- Avoid repeating recent messages.\n"
        "- Avoid repeating recent titles.\n"
        "- Avoid repeating recent opening phrases.\n"
        "- Avoid repeating recent metaphors.\n"
        "- Avoid using the same joke structure repeatedly.\n"
        "- If recent messages focused on benchmark underperformance, use another available angle such as worst asset, drawdown, ATH, deposit behavior, or no-change commentary.\n"
        "- If nothing meaningful changed since the last message, say that directly and keep the commentary lighter.\n"
        "- Be concise.\n"
        "- Output must be valid JSON matching the requested schema.\n\n"
        "Tone rules:\n"
        "- gentle: supportive, lightly funny\n"
        "- sarcastic: witty, dry, default Roastfolio tone\n"
        "- brutal: sharper, but still safe\n"
        "- degen: chaotic internet-finance humor, but no slurs, no reckless advice, no explicit trade instructions\n\n"
    )

    # Extract anti-repetition data (used in user prompt)
    forbidden_phrases = []
    recent_titles = []
    recent_punchlines = []
    if recentRoasts:
        for r in recentRoasts:
            msg = r.get("messageText", "") or r.get("message", "")
            title = r.get("title", "")
            if title:
                recent_titles.append(title)
            if msg:
                words = [w for w in msg.replace(',', '').replace('.', '').split()]
                if words:
                    forbidden_phrases.append(" ".join(words[:5]))
                sentences = [s.strip() for s in msg.replace('?', '.').replace('!', '.').split('.') if s.strip()]
                if sentences:
                    recent_punchlines.append(sentences[-1])
                    
    # Only append formatting to system prompt
    system_prompt += "FORMAT: Keep your output concise. Return the response in valid JSON matching the requested schema.\n"

    # ── 4. Prompt Type Specifics & Schemas ─────────────────────────────────────
    user_prompt_data = {
        "locale": userLocale,
        "currency": currency,
        "portfolioData": portfolioData or {},
        "behavioralSignals": behavioralSignals or {}
    }
    
    expected_output_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The generated commentary text."},
            "category": {"type": "string", "description": "A short category label for the commentary (e.g. 'benchmark_beat')."}
        },
        "required": ["text", "category"],
        "additionalProperties": False
    }

    if promptType == "daily_roast":
        user_prompt_text = (
            "Generate today's Roastfolio commentary.\n\n"
            "Context:\n"
            f"- scenarioKey: {scenarioKey}\n"
            f"- commentaryMode: {commentaryMode}\n"
            f"- messageAngle: {messageAngle}\n"
            f"- roastIntensity: {roastIntensity}\n"
            f"- outcomeType: {outcomeType}\n"
            f"- currency: {currency}\n\n"
            "Portfolio data:\n"
            f"{json.dumps(portfolioData or {}, indent=2)}\n\n"
            "Benchmark data:\n"
            f"{json.dumps(benchmarkData or {}, indent=2)}\n\n"
            "Daily movers:\n"
            f"{json.dumps({'bestAsset': (portfolioData or {}).get('best_asset'), 'worstAsset': (portfolioData or {}).get('worst_asset')}, indent=2)}\n\n"
            "Behavioral signals:\n"
            f"{json.dumps(behavioralSignals or {}, indent=2)}\n\n"
            "Recent messages shown to this user:\n"
            f"{json.dumps(recentRoasts or [], indent=2)}\n\n"
            "Do not repeat:\n"
            f"- Titles: {json.dumps(list(set(recent_titles)))}\n"
            f"- Opening phrases: {json.dumps(list(set(forbidden_phrases)))}\n"
            f"- Metaphors/jokes: {json.dumps(list(set(recent_punchlines)))}\n\n"
            "Novelty rules:\n"
            "- Do not reuse the same title.\n"
            "- Do not reuse the same first sentence structure.\n"
            "- Do not reuse the same metaphor.\n"
            "- Do not use the same punchline style as recent messages.\n"
            "- If the data has barely changed, acknowledge that instead of inventing drama.\n"
            "- Prefer the requested messageAngle.\n"
            "- Keep it concise.\n"
            "- Make it funny but useful.\n\n"
            "Return valid JSON:\n"
            "{\n"
            '  "title": string,\n'
            '  "message": string,\n'
            '  "tone": "praise" | "neutral" | "roast" | "mixed",\n'
            '  "severity": 1 | 2 | 3 | 4 | 5,\n'
            '  "mainReason": string,\n'
            '  "suggestedFocus": string | null\n'
            "}\n"
        )
        
        # Override schema for daily roast
        expected_output_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "message": {"type": "string"},
                "tone": {"type": "string", "enum": ["praise", "neutral", "roast", "mixed"]},
                "severity": {"type": "integer", "minimum": 1, "maximum": 5},
                "mainReason": {"type": "string"},
                "suggestedFocus": {"type": ["string", "null"]}
            },
            "required": ["title", "message", "tone", "severity", "mainReason"]
        }
        
    elif promptType == "monthly_report":
        user_prompt_data["benchmarkData"] = benchmarkData or {}
        if recentRoasts:
            user_prompt_data["recentRoastsContext"] = recentRoasts
        user_prompt_text = "Generate a monthly portfolio report roast focusing on 30-day trends and long-term consistency.\n"
        expected_output_schema["properties"]["summary"] = {"type": "string", "description": "A short summary of the month"}
        expected_output_schema["required"].append("summary")
        
    elif promptType == "achievement":
        user_prompt_data["achievements"] = achievements or []
        user_prompt_text = "Generate commentary for a newly unlocked user achievement/badge.\n"
        
    elif promptType == "fire_progress":
        user_prompt_data["fireProgress"] = fireProgress or {}
        user_prompt_text = "Generate commentary on the user's progress towards Financial Independence, Retire Early (FIRE).\n"
        
    elif promptType == "asset_specific":
        user_prompt_text = "Generate commentary focusing on a specific asset's performance and concentration risk.\n"
        
    else:
        user_prompt_text = "Generate general portfolio commentary.\n"

    if constraints:
        user_prompt_text += f"\nAdditional Constraints: {json.dumps(constraints)}\n"

    if promptType != "daily_roast":
        user_prompt_text += f"\nData:\n{json.dumps(user_prompt_data, indent=2)}"

    return {
        "systemPrompt": system_prompt,
        "userPrompt": user_prompt_text,
        "expectedOutputSchema": expected_output_schema
    }

def build_retry_prompt(
    base_prompt: dict,
    rejected_output: dict,
    similarity_reason: str,
    recent_roasts: list
) -> dict:
    """
    Builds a secondary prompt for retrying generation when the first attempt was too similar.
    """
    system_prompt = base_prompt["systemPrompt"]
    user_prompt = base_prompt["userPrompt"]
    
    retry_instruction = (
        "\n\n=========================================\n"
        "CRITICAL RETRY INSTRUCTION: YOUR PREVIOUS RESPONSE WAS REJECTED FOR BEING TOO SIMILAR TO RECENT HISTORY.\n"
        f"Reason for rejection: {similarity_reason}\n\n"
        "REJECTED OUTPUT:\n"
        f"- Title: {rejected_output.get('title', 'N/A')}\n"
        f"- Message: {rejected_output.get('message', 'N/A')}\n\n"
        "REQUIREMENTS FOR THIS ATTEMPT:\n"
        "1. You MUST use a completely different joke structure and angle.\n"
        "2. Do not use any metaphors, opening phrases, or words from the rejected output.\n"
        "3. Focus on an alternative angle (e.g., today's worst asset, benchmark comparisons, risk/concentration, or deposit behavior).\n"
        "4. DO NOT repeat the rejected title.\n"
    )
    
    new_user_prompt = user_prompt + retry_instruction
    
    return {
        "systemPrompt": system_prompt,
        "userPrompt": new_user_prompt,
        "expectedOutputSchema": base_prompt["expectedOutputSchema"]
    }

