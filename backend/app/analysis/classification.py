from __future__ import annotations

import re

# ── DETERMINISTIC CATEGORY OVERRIDES ──────────────────────────────────────────
# Mapping of regex patterns to (Normalized Merchant Name, Forced Category, Forced Sub/Category)
_MERCHANT_RULES = [
    (re.compile(r"\b(amazon|amzn)\b", re.I), "Amazon", "Shopping", "General"),
    (re.compile(r"\b(zomato|swiggy|zepto|blinkit|instamart|dunzo)\b", re.I), None, "Food & Dining", "Delivery/Groceries"),
    (re.compile(r"\b(uber|ola|rapido|namma\s*yatri|blusmart)\b", re.I), None, "Transportation", "Cabs"),
    (re.compile(r"\b(netflix|spotify|prime|youtube\s*premium|hotstar|sony\s*liv|zee5)\b", re.I), None, "Subscriptions", "OTT"),
    (re.compile(r"\b(lic|hdfc\s*life|icici\s*pru|sbi\s*life|max\s*life|star\s*health)\b", re.I), None, "Insurance", "Premium"),
    (re.compile(r"\b(zerodha|groww|upstox|kuvera|indmoney|angel\s*one)\b", re.I), None, "Investments", "Brokerage"),
    (re.compile(r"\b(bescom|bwssb|mahavitaran|adani\s*electricity|bses|tatapower)\b", re.I), None, "Utilities", "Electricity/Water"),
    (re.compile(r"\b(jio|airtel|vi\b|vodafone|bsnl|act\s*fibernet|hathway)\b", re.I), None, "Utilities", "Telecom/Internet"),
    (re.compile(r"\b(petrol|diesel|fuel|indian\s*oil|bpcl|hpcl|bharat\s*petroleum|hindustan\s*petroleum|shell)\b", re.I), None, "Transportation", "Fuel"),
    (re.compile(r"\b(irctc|makemytrip|goibibo|cleartrip|yatra|indigo|air\s*india|vistara|spicejet)\b", re.I), None, "Travel", "Tickets"),
    (re.compile(r"\b(apollo|netmeds|pharmeasy|1mg|practo|hospital|clinic)\b", re.I), None, "Health & Wellness", "Medical"),
]

def apply_classification_overrides(
    merchant_raw: str, current_clean: str, current_cat: str, current_sub: str
) -> tuple[str, str, str]:
    """
    Returns (merchant_clean, category, sub_category) strictly governed by dictionary rules.
    If no rule hits, returns the AI's current attempt.
    """
    clean_name = current_clean
    cat = current_cat
    sub = current_sub
    
    blob = f"{merchant_raw} {current_clean}".lower()
    
    for pattern, rule_merchant, rule_cat, rule_sub in _MERCHANT_RULES:
        match = pattern.search(blob)
        if match:
            # Normalize merchant name using rule or the matched text capitalized
            if rule_merchant:
                clean_name = rule_merchant
            else:
                clean_name = match.group(0).title()
                
            cat = rule_cat
            sub = rule_sub
            break
            
    return clean_name, cat, sub

def determine_transaction_type(blob: str, current_type: str = "unknown") -> str:
    """
    Strips the implicit rail/type out of the merchant name so it can be tracked separately.
    Returns: transfer, refund, charge, fee, interest, tax, purchase, unknown
    """
    blob = blob.lower()
    if "refund" in blob or "reversal" in blob or "cashback" in blob or "returned" in blob:
        return "refund"
    if "tax" in blob or "cgst" in blob or "sgst" in blob or "igst" in blob:
        return "tax"
    if "interest" in blob:
        return "interest"
    if "fee" in blob or "charge" in blob or "penalty" in blob or "bounce" in blob or "overdraft" in blob:
        return "fee"
    if "neft" in blob or "imps" in blob or "rtgs" in blob or "upi" in blob or "transfer" in blob or "sweep" in blob or "ft-" in blob:
        return "transfer"
    
    # If we get here, it's likely standard commercial activity or ATM
    if "atm" in blob or "cash" in blob or "pos" in blob or "purchase" in blob:
        return "purchase"
        
    return "purchase" if current_type == "unknown" else current_type
