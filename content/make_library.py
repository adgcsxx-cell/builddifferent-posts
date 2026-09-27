"""Builds content/library.json: the first 30 posts (Lessons 03-32).

All chart numbers are computed here from math or seeded simulations, never from live market data.
Run: python3 content/make_library.py
"""
import json
import math
import os
import random

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CTA = {"type": "cta"}


def r1(x):
    return round(float(x), 1)


def r2(x):
    return round(float(x), 2)


# ------------------------------------------------------------------ data ----
def drawdown_recovery():
    losses = [10, 20, 30, 40, 50, 60, 70]
    return [f"−{l}%" for l in losses], [r1((1 / (1 - l / 100) - 1) * 100) for l in losses]


def streak_equity():
    xs = list(range(0, 26))
    return xs, [[r2(100 * (1 - r) ** n) for n in xs] for r in (0.01, 0.02, 0.05)]


def p_streak(n_trades, k, q):
    dp = [0.0] * k
    dp[0] = 1.0
    hit = 0.0
    for _ in range(n_trades):
        new = [0.0] * k
        for run, pr in enumerate(dp):
            if pr == 0:
                continue
            new[0] += pr * (1 - q)
            if run + 1 >= k:
                hit += pr * q
            else:
                new[run + 1] += pr * q
        dp = new
    return hit


def binomial30():
    n = 30
    ks = list(range(8, 23))
    probs = [r2(math.comb(n, k) * 0.5 ** n * 100) for k in ks]
    return ks, probs


def compounding():
    years = list(range(0, 11))
    steady = [r1(100 * 1.1 ** t) for t in years]
    swing, v = [100.0], 100.0
    for t in range(1, 11):
        v *= 1.4 if t % 2 == 1 else 0.8
        swing.append(r1(v))
    return years, steady, swing


def breakeven():
    xs = [round(0.5 + 0.1 * i, 1) for i in range(36)]
    return xs, [r2(100 / (1 + x)) for x in xs]


def overfit_sim():
    best = None
    for seed in range(1, 400):
        rng = np.random.default_rng(seed)
        of = np.concatenate([rng.normal(0.26, 0.45, 150), rng.normal(-0.06, 1.0, 100)])
        rb = np.concatenate([rng.normal(0.11, 0.9, 150), rng.normal(0.11, 0.9, 100)])
        cof, crb = np.cumsum(of), np.cumsum(rb)
        of_oos = cof[-1] - cof[149]
        rb_oos = crb[-1] - crb[149]
        if (of_oos < -8 and rb_oos > 10 and crb[-1] > cof[-1] + 3 and cof[149] > crb[149] + 15
                and crb[149] > 8):
            best = (seed, cof, crb)
            break
    seed, cof, crb = best
    xs = list(range(0, 251))
    return xs, [0.0] + [r1(v) for v in cof], [0.0] + [r1(v) for v in crb]


def costs_sim():
    for seed in range(1, 500):
        rng = np.random.default_rng(seed)
        gross = rng.normal(250, 2600, 500)
        cg = np.cumsum(gross)
        cn = np.cumsum(gross - 200)
        if 110_000 < cg[-1] < 140_000 and 15_000 < cn[-1] < 35_000 and cn.min() > -30_000:
            xs = list(range(0, 501))
            return xs, [0.0] + [r1(v / 1000) for v in cg], [0.0] + [r1(v / 1000) for v in cn]
    raise RuntimeError("no seed")


def theta_curve():
    days = list(range(30, -1, -1))
    return days, [r1(100 * math.sqrt(t / 30)) for t in days]


def bs_call(s, k, t, vol):
    if t <= 0 or vol <= 0:
        return max(s - k, 0.0)
    d1 = (math.log(s / k) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    n = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    return s * n(d1) - k * n(d2)


def iv_curve():
    ivs = list(range(10, 41))
    return ivs, [r2(bs_call(100, 100, 30 / 365, v / 100)) for v in ivs]


def payoff_call():
    xs = list(range(80, 131))
    return xs, [float(max(s - 100, 0) - 5) for s in xs]


def payoff_put():
    xs = list(range(70, 121))
    return xs, [float(max(100 - s, 0) - 5) for s in xs]


def straddle_vs_fly():
    xs = list(range(75, 126))
    naked = [float(8 - abs(s - 100)) for s in xs]
    fly = [float(6 - min(abs(s - 100), 10)) for s in xs]
    return xs, naked, fly


def corrections_path():
    rnd = random.Random(5)
    anchors = [(0, 100), (40, 121), (58, 107), (110, 132), (150, 101), (200, 118)]
    xs, ys = [], []
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        for x in range(x0, x1):
            f = (x - x0) / (x1 - x0)
            f = 0.5 - 0.5 * math.cos(math.pi * f)
            ys.append(y0 + (y1 - y0) * f + rnd.uniform(-1.1, 1.1))
            xs.append(x)
    xs.append(200)
    ys.append(118.0)
    ys = [r1(v) for v in ys]
    # measure the two drawdowns from the actual path
    def dd(a, b):
        seg = ys[a:b]
        peak_i = max(range(len(seg)), key=lambda i: seg[i])
        trough_i = min(range(peak_i, len(seg)), key=lambda i: seg[i])
        return a + trough_i, (seg[trough_i] / seg[peak_i] - 1) * 100
    t1, d1 = dd(20, 80)
    t2, d2 = dd(90, 180)
    return xs, ys, (t1, d1), (t2, d2)


def mc_risk():
    rng = np.random.default_rng(42)
    sims, n = 20000, 200
    wins = rng.random((sims, n)) < 0.45
    med, p95 = [], []
    for r in (0.005, 0.01, 0.02, 0.03, 0.05):
        mult = np.where(wins, 1 + 1.5 * r, 1 - r)
        eq = np.cumprod(np.hstack([np.ones((sims, 1)), mult]), axis=1)
        peak = np.maximum.accumulate(eq, axis=1)
        dd = ((peak - eq) / peak).max(axis=1)
        med.append(r1(np.median(dd) * 100))
        p95.append(r1(np.percentile(dd, 95) * 100))
    return ["0.5%", "1%", "2%", "3%", "5%"], med, p95


def mc_reshuffle():
    rng = np.random.default_rng(42)
    base = np.array([1.5] * 45 + [-1.0] * 55)
    dds = []
    for _ in range(20000):
        cum = np.concatenate([[0], np.cumsum(rng.permutation(base))])
        dds.append((np.maximum.accumulate(cum) - cum).max())
    dds = np.array(dds)
    edges = [4, 6, 8, 10, 12, 14, 16, 18, 1000]
    cats = ["4–6", "6–8", "8–10", "10–12", "12–14", "14–16", "16–18", "18+"]
    vals = [r1(((dds >= a) & (dds < b)).mean() * 100) for a, b in zip(edges, edges[1:])]
    return cats, vals


# ----------------------------------------------------------------- posts ----
def posts():
    P = []

    cats, vals = drawdown_recovery()
    P.append({
        "id": "03-drawdown-recovery", "pillar": "Risk", "label": "Lesson 03 · Risk",
        "slides": [
            {"type": "cover", "kicker": "Risk math",
             "title": "Lose **50%** and you need **+100%** just to get back to zero.",
             "sub": "Why protecting capital beats chasing returns."},
            {"type": "chart", "title": "The recovery trap",
             "body": "Every loss needs a bigger gain to repair it, and the gap explodes as losses get deeper.",
             "chart": {"kind": "bar", "title": "Gain needed to recover from a loss", "categories": cats,
                       "values": vals, "value_format": "+{:.0f}%", "highlight": [4], "x_label": "Loss from peak"},
             "note": "Math: gain needed = 1 ÷ (1 − loss) − 1. Not market data."},
            {"type": "text", "title": "Why it happens",
             "body": "Losses and gains are percentages of **different** starting amounts.\n"
                     "- Start with ₹1,00,000 and lose 50%: you have ₹50,000.\n"
                     "- A 50% gain on ₹50,000 only gets you to ₹75,000.\n"
                     "- You need +100% (another ₹50,000) to be back at ₹1,00,000.",
             "callout": "Small losses are cheap to fix. Big losses can take years."},
            {"type": "checklist", "title": "How systematic traders keep losses small",
             "items": ["Decide the maximum loss per trade **before** you enter (e.g. 1% of capital).",
                       "Set a daily or weekly loss limit, and stop trading when it's hit.",
                       "Cut position size after a drawdown instead of trying to win it back.",
                       "Never add to a losing position without a written plan."]},
            CTA,
        ],
        "caption": "A 50% loss needs a 100% gain to recover. That's not opinion, it's arithmetic.\n\n"
                   "When you lose, the next gain is calculated on a smaller base. So the deeper the hole, the steeper the climb:\n"
                   "→ −10% needs +11%\n→ −30% needs +43%\n→ −50% needs +100%\n→ −70% needs +233%\n\n"
                   "This is why professional traders obsess over the downside first. Small, controlled losses are easy to repair. "
                   "One big loss can undo years of good work.\n\n"
                   "Save this for the next time you're tempted to skip a stop-loss.",
        "hashtags": ["#riskmanagement", "#tradingpsychology", "#stockmarketindia", "#tradingeducation", "#optionstrading"],
    })

    P.append({
        "id": "04-what-is-a-system", "pillar": "Systems", "label": "Lesson 04 · Systems",
        "slides": [
            {"type": "cover", "kicker": "Systematic trading",
             "title": "A trading **system** is just four decisions, made **before** the market opens.",
             "sub": "If one is missing, you're improvising."},
            {"type": "checklist", "title": "The 4 parts of every system",
             "items": ["**Setup:** which market, timeframe and conditions you trade.",
                       "**Entry:** the exact rule that gets you in.",
                       "**Exit:** where you take the loss, and where you take profit.",
                       "**Size:** how much you risk on each trade."]},
            {"type": "text", "title": "Why rules beat instinct",
             "body": "Under pressure, the brain takes shortcuts: it holds losers, cuts winners and chases moves.\n"
                     "Written rules make the decision **before** emotions arrive. They also let you test an idea on "
                     "past data and measure whether it actually works.",
             "callout": "If you can't write it down, you can't test it."},
            {"type": "text", "title": "A simple example",
             "body": "Illustrative only, not a recommendation:\n"
                     "- **Setup:** index above its 50-day average\n"
                     "- **Entry:** buy on a close above the previous day's high\n"
                     "- **Exit:** stop below the previous day's low; target 2× the risk\n"
                     "- **Size:** risk 1% of capital per trade",
             "callout": "Specific enough that two people would take exactly the same trade."},
            CTA,
        ],
        "caption": "Most traders don't have a system. They have a feeling.\n\n"
                   "A real trading system answers four questions in advance:\n"
                   "1. Setup: what am I trading, and when?\n2. Entry: what exactly gets me in?\n"
                   "3. Exit: where do I accept I'm wrong, and where do I take profit?\n4. Size: how much am I risking?\n\n"
                   "Write all four down before the market opens. If two people could read your rules and take different "
                   "trades, the rules aren't finished.\n\nWhich of the four do you struggle with most? Tell me in the comments.",
        "hashtags": ["#systematictrading", "#tradingstrategy", "#algotrading", "#tradingeducation", "#stockmarketindia"],
    })

    xs, ys = payoff_call()
    P.append({
        "id": "05-call-option-payoff", "pillar": "Options", "label": "Lesson 05 · Options",
        "slides": [
            {"type": "cover", "kicker": "Options basics",
             "title": "A call option is the **right** to buy, not the obligation.",
             "sub": "What a call buyer can make or lose at expiry."},
            {"type": "text", "title": "A call option in plain words",
             "body": "- You pay a **premium** today.\n"
                     "- In return, you get the right to buy at a fixed price (the **strike**) until expiry.\n"
                     "- If the price ends above the strike, that right has value.\n"
                     "- If it ends below, the option expires worthless and you lose only the premium."},
            {"type": "chart", "title": "Payoff at expiry", "body": "Illustrative call: strike 100, premium 5.",
             "chart": {"kind": "line", "title": "Profit or loss per unit", "x": xs,
                       "series": [{"name": "Long call", "values": ys, "focus": True}],
                       "zero_line": True, "area_base": 0, "y_format": "{:g}", "x_label": "Price at expiry",
                       "x_ticks": [80, 90, 100, 110, 120, 130],
                       "vlines": [{"x": 100, "label": "Strike 100", "side": "left"}],
                       "points": [{"x": 105, "label": "Break-even 105", "dx": 22, "dy": -60},
                                  {"x": 88, "label": "Max loss: the premium (−5)", "dx": -10, "dy": 26}]},
             "note": "Illustrative numbers. Ignores brokerage and taxes."},
            {"type": "checklist", "title": "3 numbers every call buyer should know",
             "items": ["**Max loss** = the premium you paid.",
                       "**Break-even** = strike + premium.",
                       "**Time** works against you: the premium shrinks as expiry gets closer, if nothing else changes."]},
            CTA,
        ],
        "caption": "Options sound complicated. The core idea isn't.\n\n"
                   "A call option gives you the right, not the obligation, to buy at a fixed price (the strike) before expiry. "
                   "You pay a premium for that right.\n\n"
                   "In the example (strike 100, premium 5):\n→ Below 100 at expiry: the option expires worthless. You lose 5, never more.\n"
                   "→ At 105: you break even.\n→ Above 105: profit grows with the price.\n\n"
                   "The catch is time. Every day, part of that premium melts away. That's the next lesson in this series.\n\n"
                   "Follow for one clear lesson a day.",
        "hashtags": ["#optionstrading", "#optionsbasics", "#derivatives", "#tradingeducation", "#stockmarketindia"],
    })

    P.append({
        "id": "06-process-vs-outcome", "pillar": "Psychology", "label": "Lesson 06 · Psychology",
        "slides": [
            {"type": "cover", "kicker": "Trading psychology", "title": "A winning trade can be a **bad** trade.",
             "sub": "Judge the decision, not the result."},
            {"type": "matrix", "title": "Process vs outcome",
             "x_axis": ["Good outcome", "Bad outcome"], "y_axis": ["Good process", "Bad process"],
             "cells": [[{"title": "Deserved win", "sub": "Followed the plan and it worked. Repeat it."},
                        {"title": "Bad luck", "sub": "Followed the plan and lost anyway. Accept it, move on."}],
                       [{"title": "Dumb luck", "sub": "Broke the rules and won. The most **dangerous** box."},
                        {"title": "Deserved loss", "sub": "Broke the rules and lost. Fix the process."}]],
             "highlight": [1, 0],
             "body": "Dumb luck is dangerous because it teaches you to repeat the mistake."},
            {"type": "text", "title": "Why this matters",
             "body": "Even a system with a real edge can lose 4 or 5 trades in a row. A trade with no edge can still win.\n"
                     "Over a few trades, luck dominates. Over hundreds, process does.\n"
                     "So score yourself on whether you followed your rules, not on today's P&L.",
             "callout": "Good process + enough trades = the edge shows up."},
            {"type": "checklist", "title": "After every trade, ask",
             "items": ["Did I take a trade my rules allowed?", "Was my size what the plan said?",
                       "Did I exit where I planned, or did I improvise?",
                       "Would I take this exact trade again tomorrow?"]},
            CTA,
        ],
        "caption": "The market pays you randomly in the short run. That's why results are a terrible teacher.\n\n"
                   "There are four kinds of trades:\n✅ Good process, good outcome: deserved win\n"
                   "☑️ Good process, bad outcome: bad luck\n⚠️ Bad process, good outcome: dumb luck\n"
                   "❌ Bad process, bad outcome: deserved loss\n\n"
                   "The dangerous one is dumb luck. You broke your rules, got paid, and now your brain wants to do it again.\n\n"
                   "Grade your trades on process. Over enough trades, the P&L follows.",
        "hashtags": ["#tradingpsychology", "#tradingmindset", "#tradingdiscipline", "#systematictrading", "#stockmarketindia"],
    })

    xs, (e1, e2, e5) = streak_equity()
    P.append({
        "id": "07-risk-per-trade", "pillar": "Risk", "label": "Lesson 07 · Risk",
        "slides": [
            {"type": "cover", "kicker": "Position sizing",
             "title": "At **5%** risk per trade, 10 losses in a row wipe out **40%** of your account.",
             "sub": "At 1% risk, the same streak costs under 10%."},
            {"type": "chart", "title": "Equity after a losing streak",
             "body": "The same losing streak at three different bet sizes.",
             "chart": {"kind": "line", "title": "Account value left (%)", "x": xs,
                       "series": [{"name": "Risk 1% per trade", "values": e1, "focus": True, "end_label": "1%"},
                                  {"name": "2%", "values": e2, "end_label": "2%"},
                                  {"name": "5%", "values": e5, "end_label": "5%"}],
                       "area": False, "y_format": "{:.0f}%", "y_ticks": [20, 40, 60, 80, 100],
                       "x_label": "Losses in a row", "x_ticks": [0, 5, 10, 15, 20, 25],
                       "points": [{"series": 0, "x": 10, "label": "−9.6%", "dx": 16, "dy": -58},
                                  {"series": 2, "x": 10, "label": "−40%", "dx": -24, "dy": 26}]},
             "note": "Math: account left = (1 − risk) ^ losses. Not market data."},
            {"type": "stat", "kicker": "Losses in a row to lose 20%", "value": "23",
             "label": "losing trades in a row at 1% risk per trade.",
             "body": "At 2% risk it takes just 12. At 5% risk, only 5."},
            {"type": "text", "title": "Why small size is a superpower",
             "body": "Losing streaks don't mean your system is broken. They're a normal part of trading.\n"
                     "Small risk per trade turns a normal streak into an inconvenience instead of a disaster, and you're "
                     "still in the game when the good trades come.",
             "callout": "Size so your worst streak is survivable, not so your best trade is huge."},
            CTA,
        ],
        "caption": "How much you risk per trade matters more than how you pick trades.\n\n"
                   "Take the same streak of 10 losing trades:\n→ Risking 1% per trade: down about 10%\n"
                   "→ Risking 2%: down about 18%\n→ Risking 5%: down about 40%\n\n"
                   "To lose 20% of your account you'd need 23 losses in a row at 1% risk, but only 5 at 5% risk.\n\n"
                   "Streaks happen to every trader and every system. Your position size decides whether a streak is a bad week "
                   "or the end of your account.\n\nWhat do you risk per trade? Be honest in the comments.",
        "hashtags": ["#riskmanagement", "#positionsizing", "#tradingpsychology", "#stockmarketindia", "#optionstrading"],
    })

    ks, probs = binomial30()
    P.append({
        "id": "08-sample-size", "pillar": "Systems", "label": "Lesson 08 · Systems",
        "slides": [
            {"type": "cover", "kicker": "Backtesting", "title": "**30 trades** prove almost nothing.",
             "sub": "A coin flip can look like a genius strategy over a small sample."},
            {"type": "chart", "title": "A 50/50 strategy over 30 trades",
             "body": "Amber: a 60%+ win rate, which a zero-edge strategy shows 18% of the time by pure chance.",
             "chart": {"kind": "bar", "title": "Chance of each result (%)", "categories": ks, "values": probs,
                       "value_format": "{:.0f}%", "y_format": "{:.0f}%", "highlight_range": [10, 14],
                       "label_all": False, "show_y_axis": True, "label_every": 2, "bar_ratio": 0.62,
                       "x_label": "Winning trades out of 30"},
             "note": "Binomial math for a fair 50/50 strategy. Not market data."},
            {"type": "stat", "value": "18%",
             "label": "chance a coin-flip strategy shows a 60%+ win rate over 30 trades.",
             "body": "The usual range of outcomes (95% of the time) runs from 10 to 20 wins, or 33% to 67%, with zero real edge."},
            {"type": "checklist", "title": "Before you trust a backtest",
             "items": ["Aim for **hundreds** of trades, not dozens.",
                       "Check different market periods: trending, choppy and crashing.",
                       "Compare against a simple benchmark or random entries.",
                       "Be suspicious of any result that looks too smooth."]},
            CTA,
        ],
        "caption": "Your strategy won 19 of its last 30 trades. Is it good?\n\n"
                   "Maybe. Or maybe it's a coin flip having a lucky month.\n\n"
                   "If a strategy has zero edge (a true 50% win rate), there's still an 18% chance it wins 18 or more of 30 trades. "
                   "That's a 60%+ win rate from pure luck, roughly 1 time in 5.\n\n"
                   "Small samples are noisy. Before trusting any system, backtest or live, you need enough trades for the edge "
                   "to stand out from the noise. Think hundreds, across different market conditions.\n\n"
                   "Save this before you judge your next strategy on one good month.",
        "hashtags": ["#backtesting", "#systematictrading", "#algotrading", "#quanttrading", "#tradingeducation"],
    })

    years, steady, swing = compounding()
    P.append({
        "id": "09-volatility-drag", "pillar": "Fundamentals", "label": "Lesson 09 · Fundamentals",
        "slides": [
            {"type": "cover", "kicker": "Compounding",
             "title": "+50% then −50% isn't break-even. It's **−25%**.", "sub": "How volatility quietly eats returns."},
            {"type": "text", "title": "The math",
             "body": "- Start: ₹1,00,000\n- Year 1, +50%: ₹1,50,000\n- Year 2, −50%: ₹75,000\n"
                     "The average return looks like 0%, but you're down 25%. Big swings drag down what you actually earn.",
             "callout": "What compounds is your **real** (geometric) return, not the simple average."},
            {"type": "chart", "title": "Same average, different outcome",
             "body": "Both paths average +10% a year. Only one of them compounds like it.",
             "chart": {"kind": "line", "title": "Value of ₹100", "x": years,
                       "series": [{"name": "Steady +10% a year", "values": steady, "focus": True},
                                  {"name": "Swinging +40% / −20%", "values": swing}],
                       "area": False, "y_format": "₹{:.0f}", "x_label": "Years", "x_ticks": [0, 2, 4, 6, 8, 10],
                       "points": [{"series": 0, "x": 10, "label": "₹259", "dx": -110, "dy": -20},
                                  {"series": 1, "x": 10, "label": "₹176", "dx": -110, "dy": 18}]},
             "note": "Illustrative math, not market data."},
            {"type": "checklist", "title": "What this means for traders",
             "items": ["Avoiding big losses matters more than catching big wins.",
                       "With the same average return, lower volatility compounds faster.",
                       "Judge performance by compound growth (CAGR), not average returns.",
                       "Position sizing is how you control volatility."]},
            CTA,
        ],
        "caption": "Two strategies both average +10% a year. After 10 years, one turns ₹100 into ₹259. The other, only ₹176.\n\n"
                   "The difference is volatility.\n\n"
                   "A +40% year followed by a −20% year averages +10%, but compounds to only about +5.8% a year. "
                   "Big swings drag your real (geometric) return below the simple average.\n\n"
                   "The classic example: +50% then −50% leaves you down 25%, not flat.\n\n"
                   "That's why controlling drawdowns isn't just about comfort. It's math. Smoother returns compound faster.",
        "hashtags": ["#compounding", "#riskmanagement", "#personalfinance", "#stockmarketindia", "#tradingeducation"],
    })

    xs, ys = breakeven()
    P.append({
        "id": "10-breakeven-win-rate", "pillar": "Risk", "label": "Lesson 10 · Risk",
        "slides": [
            {"type": "cover", "kicker": "Risk vs reward",
             "title": "With **2:1** reward to risk, you can be wrong **2 times out of 3** and still break even.",
             "sub": "A win rate means nothing without the payoff."},
            {"type": "chart", "title": "Break-even win rate",
             "body": "The more you win relative to what you lose, the less often you need to be right.",
             "chart": {"kind": "line", "title": "Win rate needed to break even", "x": xs,
                       "series": [{"name": "Break-even", "values": ys, "focus": True}],
                       "y_format": "{:.0f}%", "y_ticks": [0, 20, 40, 60, 80], "x_format": "{:g}:1",
                       "x_ticks": [0.5, 1, 2, 3, 4], "x_label": "Reward to risk", "end_dots": False,
                       "points": [{"x": 1.0, "label": "1:1 needs 50%", "dx": 20, "dy": -12},
                                  {"x": 2.0, "label": "2:1 needs 33%", "dx": 20, "dy": -62},
                                  {"x": 3.0, "label": "3:1 needs 25%", "dx": 20, "dy": -62}]},
             "note": "Math: break-even win rate = 1 ÷ (1 + reward/risk). Before costs."},
            {"type": "formula", "title": "The formula", "formula": "Break-even win rate = 1 ÷ (1 + R)",
             "body": "- **R** = average win ÷ average loss\n- 1:1 needs 50% winners\n- 2:1 needs 33%\n- 3:1 needs 25%\n"
                     "Costs (brokerage, taxes, slippage) push the real number higher."},
            {"type": "text", "title": "The trade-off",
             "body": "Bigger targets get hit less often. Tighter targets get hit more often, but pay less.\n"
                     "Neither is better on its own. What matters is whether your **actual** win rate is above the "
                     "break-even rate for your **actual** payoff.",
             "callout": "Track both numbers. One without the other means nothing."},
            CTA,
        ],
        "caption": "\"My strategy wins 70% of the time.\" Great, but how much do you win versus lose?\n\n"
                   "A win rate only means something next to the payoff:\n"
                   "→ Win the same as you lose (1:1): you need 50% winners to break even.\n"
                   "→ Win twice what you lose (2:1): just 33%.\n→ Win three times (3:1): only 25%.\n\n"
                   "The formula: break-even win rate = 1 ÷ (1 + R), where R is your average win divided by your average loss. "
                   "Add costs and you need a little more.\n\nKnow both numbers for your own trading. Which one do you track today?",
        "hashtags": ["#riskmanagement", "#riskreward", "#tradingstrategy", "#tradingeducation", "#stockmarketindia"],
    })

    xs, of, rb = overfit_sim()
    P.append({
        "id": "11-overfitting", "pillar": "Systems", "label": "Lesson 11 · Systems",
        "slides": [
            {"type": "cover", "kicker": "Backtesting traps",
             "title": "The **perfect** backtest is usually the one that fails live.",
             "sub": "What over-fitting looks like."},
            {"type": "chart", "title": "Backtest vs live", "body": "Two strategies, tested on the same past data.",
             "chart": {"kind": "line", "title": "Cumulative result (R)", "x": xs,
                       "series": [{"name": "Robust", "values": rb, "focus": True, "end_label": "Robust"},
                                  {"name": "Over-tuned", "values": of, "end_label": "Over-tuned"}],
                       "area": False, "y_format": "{:.0f}R", "x_label": "Trade number",
                       "x_ticks": [0, 50, 100, 150, 200, 250],
                       "regions": [{"x0": 150, "x1": 250, "label": "Live", "label_pos": "bottom"}],
                       "vlines": [{"x": 150, "label": "Backtest", "side": "left", "label_pos": "bottom"}]},
             "note": "Illustrative simulation, not real strategies. R = amount risked per trade."},
            {"type": "text", "title": "How over-fitting happens",
             "body": "You test 200 settings and keep the best one. But the best one on past data is often the one that "
                     "best fitted the **noise**, not a real pattern.\nNoise doesn't repeat, so the edge disappears live.",
             "callout": "More parameters and more tweaks mean more ways to fool yourself."},
            {"type": "checklist", "title": "Guard rails",
             "items": ["Keep rules simple, with few parameters.",
                       "Hold back data the strategy has never seen (out-of-sample).",
                       "Check that nearby settings work too, not just one magic value.",
                       "Expect live results to be worse than the backtest, and size for it."]},
            CTA,
        ],
        "caption": "If your backtest equity curve looks like a staircase to heaven, be careful.\n\n"
                   "When you try hundreds of settings and keep the best, you usually find the one that best matched past noise. "
                   "It looks brilliant on old data and falls apart on new data. That's over-fitting.\n\n"
                   "Robust strategies look less exciting in testing, but they keep working when the market changes.\n\n"
                   "Simple rules. Out-of-sample testing. Settings that work across a range, not at one magic number.\n\n"
                   "Have you ever had a backtest fall apart live?",
        "hashtags": ["#backtesting", "#algotrading", "#systematictrading", "#quanttrading", "#tradingstrategy"],
    })

    days, tv = theta_curve()
    P.append({
        "id": "12-time-decay", "pillar": "Options", "label": "Lesson 12 · Options",
        "slides": [
            {"type": "cover", "kicker": "Options basics",
             "title": "An option loses value **every day**, and fastest in its final week.",
             "sub": "That's time decay, also called theta."},
            {"type": "chart", "title": "Time value vs days to expiry",
             "body": "An at-the-money option, with nothing else changing.",
             "chart": {"kind": "line", "title": "Time value left (%)", "x": days,
                       "series": [{"name": "Time value", "values": tv, "focus": True}],
                       "x_reverse": True, "y_format": "{:.0f}%", "y_ticks": [0, 25, 50, 75, 100],
                       "x_ticks": [30, 25, 20, 15, 10, 5, 0], "x_label": "Days to expiry",
                       "points": [{"x": 15, "label": "Halfway: 71% left", "dx": 20, "dy": -64},
                                  {"x": 7, "label": "7 days: 48% left", "dx": 20, "dy": -64}]},
             "note": "Simplified model: time value follows √(days left). Real prices also depend on volatility."},
            {"type": "stat", "value": "48%",
             "label": "of the time value is still left with 7 days to go.",
             "body": "Then it melts to zero in the final week. In this simplified model, the last 7 days take about half the value."},
            {"type": "checklist", "title": "What it means",
             "items": ["Option **buyers** fight the clock: the move has to come soon.",
                       "Option **sellers** collect the decay, but carry the risk of a big move.",
                       "Near expiry, decay speeds up, and so do price swings (gamma).",
                       "Always know how many days are left on your option."]},
            CTA,
        ],
        "caption": "Every option has an expiry date, and the clock never stops.\n\n"
                   "The part of an option's price that comes from time (its time value) shrinks every day, and not evenly: "
                   "it speeds up as expiry gets closer.\n\n"
                   "In the simplified model shown, an at-the-money option still has about 48% of its time value with 7 days left, "
                   "then loses all of it in the final week.\n\n"
                   "That's why buyers need the move to happen fast, and why sellers are paid to wait (while carrying the risk "
                   "of a sharp move).\n\nNext time you buy an option, check how many days you're paying for.",
        "hashtags": ["#optionstrading", "#optionsbasics", "#thetadecay", "#tradingeducation", "#stockmarketindia"],
    })

    P.append({
        "id": "13-revenge-trading", "pillar": "Psychology", "label": "Lesson 13 · Psychology",
        "slides": [
            {"type": "cover", "kicker": "Trading psychology",
             "title": "The most expensive trade is the one you take to **win it back**.",
             "sub": "How revenge trading works, and how to break the loop."},
            {"type": "cycle", "title": "The revenge loop",
             "steps": ["A loss hits", "Urge to **win it back** now", "Bigger size, weaker setup", "Bigger loss"],
             "center": "Repeat", "highlight": 1, "body": "Every lap makes the next one worse."},
            {"type": "text", "title": "Why it happens",
             "body": "Losses feel roughly twice as painful as equal gains feel good (loss aversion), so the brain wants "
                     "the pain gone **now**.\nYou skip your rules, trade bigger and take setups you'd normally ignore. "
                     "The market doesn't know you're trying to get even.",
             "callout": "After a loss, the goal is to trade well, not to get even."},
            {"type": "checklist", "title": "Circuit breakers that work",
             "items": ["A **daily loss limit**: hit it and you're done for the day.",
                       "Stop after 2 or 3 losses in a row and step away.",
                       "Never increase size to recover a loss.",
                       "Write down what happened before you take the next trade."]},
            CTA,
        ],
        "caption": "You take a loss. It stings. Now you want it back, today.\n\n"
                   "So you size up, take a setup you'd normally skip, and lose again, bigger this time. "
                   "That's the revenge loop, and it has emptied more trading accounts than bad strategies ever have.\n\n"
                   "The fix isn't willpower. It's rules decided in advance:\n→ A daily loss limit that ends your day\n"
                   "→ A pause after 2–3 losses in a row\n→ Size never goes up to recover a loss\n\n"
                   "The market will be open tomorrow. Make sure your account is too.\n\n"
                   "Save this, and set your daily loss limit tonight.",
        "hashtags": ["#tradingpsychology", "#revengetrading", "#tradingdiscipline", "#riskmanagement", "#stockmarketindia"],
    })

    P.append({
        "id": "14-expectancy", "pillar": "Risk", "label": "Lesson 14 · Risk",
        "slides": [
            {"type": "cover", "kicker": "Expectancy", "title": "An **80% win rate** can still lose money.",
             "sub": "The one number that tells you if a strategy pays."},
            {"type": "compare", "title": "Which one would you trade?",
             "cards": [{"name": "Strategy A", "rows": [["Win rate", "80%"], ["Average win", "₹500"],
                                                       ["Average loss", "₹2,500"]],
                        "result": "−₹100", "pill": "Negative edge", "good": False},
                       {"name": "Strategy B", "rows": [["Win rate", "35%"], ["Average win", "₹3,000"],
                                                       ["Average loss", "₹1,000"]],
                        "result": "+₹400", "pill": "Positive edge", "good": True}],
             "body": "A feels better, because it wins most days, and still loses money over time. Illustrative numbers."},
            {"type": "formula", "title": "Expectancy", "formula": "(Win % × Avg win)\n− (Loss % × Avg loss)",
             "body": "- A: (0.80 × 500) − (0.20 × 2,500) = **−₹100** per trade\n"
                     "- B: (0.35 × 3,000) − (0.65 × 1,000) = **+₹400** per trade\n"
                     "Positive expectancy after costs is what makes a strategy worth trading."},
            {"type": "text", "title": "Why high win rates fool us",
             "body": "Frequent small wins feel great, and one big loss is easy to blame on bad luck. Low win-rate "
                     "strategies feel painful because you're wrong most of the time, even while making money.\n"
                     "Your feelings follow the win rate. Your account follows expectancy.",
             "callout": "Measure expectancy over at least 100 trades."},
            CTA,
        ],
        "caption": "Strategy A wins 80% of its trades. Strategy B wins only 35%. Which one makes money?\n\nB does.\n"
                   "→ A: wins ₹500 on average, loses ₹2,500. Expectancy: −₹100 per trade.\n"
                   "→ B: wins ₹3,000 on average, loses ₹1,000. Expectancy: +₹400 per trade.\n\n"
                   "Expectancy = (win % × average win) − (loss % × average loss). It tells you what one trade is worth, on average, "
                   "over many trades.\n\nA high win rate feels great, but feelings don't pay. Know your expectancy after costs.\n\n"
                   "(Illustrative numbers.)",
        "hashtags": ["#riskmanagement", "#tradingstrategy", "#systematictrading", "#tradingeducation", "#stockmarketindia"],
    })

    xs, cg, cn = costs_sim()
    P.append({
        "id": "15-costs", "pillar": "Systems", "label": "Lesson 15 · Systems",
        "slides": [
            {"type": "cover", "kicker": "Hidden costs",
             "title": "Costs can turn a winning strategy into a **losing** one.",
             "sub": "Brokerage, taxes and slippage add up, trade after trade."},
            {"type": "chart", "title": "Same trades, before and after costs",
             "body": "An illustrative strategy that trades often with a small edge.",
             "chart": {"kind": "line", "title": "Cumulative P&L (₹ thousand)", "x": xs,
                       "series": [{"name": "After costs", "values": cn, "focus": True},
                                  {"name": "Before costs", "values": cg}],
                       "area": False, "zero_line": True, "y_format": "₹{:.0f}k", "x_label": "Trade number",
                       "x_ticks": [0, 100, 200, 300, 400, 500]},
             "note": "Simulation: +₹250 average per trade before costs, ₹200 of costs per trade."},
            {"type": "stat", "value": "80%", "label": "of the edge in this example goes to costs.",
             "body": "₹250 average profit per trade before costs, ₹200 in costs. What's left is ₹50, and one bad month can erase it."},
            {"type": "checklist", "title": "Protect your edge",
             "items": ["Include realistic brokerage, taxes and slippage **in every backtest**.",
                       "The more often you trade, the bigger the edge you need.",
                       "Use limit orders where sensible to reduce slippage.",
                       "Track your real cost per trade from your contract notes."]},
            CTA,
        ],
        "caption": "Your strategy makes ₹250 per trade on average. Costs take ₹200. You're left with ₹50.\n\n"
                   "In a backtest without costs, that looks like a great system. In real life, 80% of the edge is gone before it "
                   "reaches your account.\n\n"
                   "Brokerage, exchange charges, taxes and slippage are small on one trade. Over hundreds of trades, they're often "
                   "the difference between a strategy that works and one that doesn't. The more often you trade, the more they matter.\n\n"
                   "Always backtest with realistic costs, and check your actual contract notes.",
        "hashtags": ["#algotrading", "#backtesting", "#systematictrading", "#tradingcosts", "#stockmarketindia"],
    })

    P.append({
        "id": "16-what-is-an-index", "pillar": "Fundamentals", "label": "Lesson 16 · Fundamentals",
        "slides": [
            {"type": "cover", "kicker": "Market basics", "title": "What the **Nifty 50** actually measures.",
             "sub": "An index, explained in 60 seconds."},
            {"type": "text", "title": "An index is a basket",
             "body": "- It tracks a group of stocks with a single number.\n"
                     "- The Nifty 50 follows 50 large companies listed on the NSE.\n"
                     "- When the basket's total value rises, the index rises.\n"
                     "- It started from a base value of 1,000 in November 1995."},
            {"type": "text", "title": "Bigger companies count more",
             "body": "The Nifty 50 is weighted by **free-float market capitalisation**: company size, counting only the "
                     "shares available for trading (for example, excluding promoter holdings).\n"
                     "So a 1% move in a heavyweight moves the index far more than a 1% move in the smallest member.",
             "callout": "A handful of large stocks can move the whole index."},
            {"type": "checklist", "title": "Worth knowing",
             "items": ["The list isn't permanent: NSE reviews it **twice a year**.",
                       "You can't buy the index itself; you use index funds, ETFs, futures or options.",
                       "The Sensex is the same idea on the BSE, with 30 companies.",
                       "The index going up doesn't mean every member went up."]},
            CTA,
        ],
        "caption": "You hear \"Nifty is up 1%\" every day. But what is it actually measuring?\n\n"
                   "The Nifty 50 is a basket of 50 large companies on the NSE, turned into one number. It's weighted by free-float "
                   "market capitalisation, so the biggest companies (counting only shares available to trade) have the most influence.\n\n"
                   "A few things most beginners don't know:\n→ The members are reviewed twice a year, so the basket changes\n"
                   "→ You can't buy the index itself; you use index funds, ETFs, futures or options\n"
                   "→ The Sensex is the BSE's version, with 30 companies\n\nSave this for anyone just getting started.",
        "hashtags": ["#nifty50", "#stockmarketindia", "#sensex", "#investingbasics", "#tradingeducation"],
    })

    xs, ys = payoff_put()
    P.append({
        "id": "17-put-option-payoff", "pillar": "Options", "label": "Lesson 17 · Options",
        "slides": [
            {"type": "cover", "kicker": "Options basics", "title": "A put option works like **insurance** against a fall.",
             "sub": "What a put buyer can make or lose at expiry."},
            {"type": "text", "title": "A put option in plain words",
             "body": "- You pay a **premium** today.\n"
                     "- You get the right to sell at a fixed price (the **strike**) until expiry.\n"
                     "- If the price ends below the strike, that right has value.\n"
                     "- If it ends above, the option expires worthless and you lose only the premium."},
            {"type": "chart", "title": "Payoff at expiry", "body": "Illustrative put: strike 100, premium 5.",
             "chart": {"kind": "line", "title": "Profit or loss per unit", "x": xs,
                       "series": [{"name": "Long put", "values": ys, "focus": True}],
                       "zero_line": True, "area_base": 0, "y_format": "{:g}", "x_label": "Price at expiry",
                       "x_ticks": [70, 80, 90, 100, 110, 120], "end_dots": False,
                       "vlines": [{"x": 100, "label": "Strike 100", "side": "right"}],
                       "points": [{"x": 95, "label": "Break-even 95", "dx": 22, "dy": -62},
                                  {"x": 108, "label": "Max loss: −5", "dx": -10, "dy": 26}]},
             "note": "Illustrative numbers. Ignores brokerage and taxes."},
            {"type": "checklist", "title": "The put buyer's cheat sheet",
             "items": ["**Max loss** = the premium you paid.", "**Break-even** = strike − premium.",
                       "Used to profit from a fall, or to **protect** an existing position.",
                       "Like any option, it loses time value every day."]},
            CTA,
        ],
        "caption": "If a call is a bet on a rise, a put is the mirror image.\n\n"
                   "A put option gives you the right (not the obligation) to sell at a fixed price, the strike, before expiry. "
                   "You pay a premium for it.\n\nExample (strike 100, premium 5):\n"
                   "→ Above 100 at expiry: it expires worthless. You lose 5, never more.\n→ At 95: break-even.\n"
                   "→ Below 95: profit grows as the price falls.\n\n"
                   "Many investors use puts like insurance: a small, known cost to limit the damage from a big fall.\n\n"
                   "Coming up: why hedges matter for option sellers.",
        "hashtags": ["#optionstrading", "#optionsbasics", "#hedging", "#tradingeducation", "#stockmarketindia"],
    })

    streak_cats = ["3+", "4+", "5+", "6+", "7+", "8+", "9+", "10+"]
    s50 = [r1(p_streak(100, k, 0.5) * 100) for k in range(3, 11)]
    P.append({
        "id": "18-losing-streaks", "pillar": "Risk", "label": "Lesson 18 · Risk",
        "slides": [
            {"type": "cover", "kicker": "Losing streaks",
             "title": "Even a **60% win rate** has a 46% chance of 5 losses in a row within 100 trades.",
             "sub": "Streaks are normal. Plan for them."},
            {"type": "chart", "title": "Losing streaks in 100 trades",
             "body": "At a 50% win rate, the chance of seeing at least this many losses in a row.",
             "chart": {"kind": "bar", "title": "Probability (50% win rate)", "categories": streak_cats,
                       "values": s50, "value_format": "{:.0f}%", "highlight": [2], "x_label": "Losses in a row"},
             "note": "Exact probability math for 100 independent trades. Not market data."},
            {"type": "text", "title": "It depends on your win rate",
             "body": "Chance of 5+ losses in a row within 100 trades:\n"
                     f"- 40% win rate: **{p_streak(100, 5, 0.6) * 100:.0f}%**\n"
                     f"- 50% win rate: **{p_streak(100, 5, 0.5) * 100:.0f}%**\n"
                     f"- 60% win rate: **{p_streak(100, 5, 0.4) * 100:.0f}%**\n"
                     f"At a 40% win rate, the chance of 8+ in a row is **{p_streak(100, 8, 0.6) * 100:.0f}%**, a coin flip.",
             "callout": "If you'd quit after 5 losses in a row, you'd quit almost every strategy."},
            {"type": "checklist", "title": "Be ready for your streak",
             "items": ["Know your system's win rate and the streaks it implies.",
                       "Size so that 10 losses in a row is survivable.",
                       "Decide in advance what would **really** mean the system is broken (e.g. a drawdown limit).",
                       "Don't change the rules in the middle of a streak."]},
            CTA,
        ],
        "caption": "Five losses in a row doesn't mean your strategy is broken. It usually means you've taken enough trades.\n\n"
                   "Over 100 trades, the chance of seeing at least 5 losses in a row:\n"
                   f"→ 40% win rate: {p_streak(100, 5, 0.6) * 100:.0f}%\n→ 50% win rate: {p_streak(100, 5, 0.5) * 100:.0f}%\n"
                   f"→ 60% win rate: {p_streak(100, 5, 0.4) * 100:.0f}%\n\n"
                   "Even good systems go through ugly stretches. Traders who don't know this abandon good strategies at exactly "
                   "the wrong time.\n\nWork out what's normal for your system before the streak arrives. Then size so you can survive it.",
        "hashtags": ["#riskmanagement", "#tradingpsychology", "#systematictrading", "#tradingeducation", "#stockmarketindia"],
    })

    P.append({
        "id": "19-walk-forward", "pillar": "Systems", "label": "Lesson 19 · Systems",
        "slides": [
            {"type": "cover", "kicker": "Testing like a pro",
             "title": "Don't test on the data you tuned on. **Walk forward.**",
             "sub": "The simplest way to catch a fake edge."},
            {"type": "windows", "title": "Walk-forward testing", "total": 12,
             "rows": [[0, 6, 8], [2, 8, 10], [4, 10, 12]],
             "labels": {"train": "Build (tune the rules)", "test": "Test (unseen data)"}, "axis_label": "Time",
             "body": "Tune on one period, then test on the next period the rules have never seen. Slide forward and repeat."},
            {"type": "text", "title": "Why it works",
             "body": "Every test period is data the strategy never saw while it was being tuned, just like live trading.\n"
                     "Join the test periods together and you get a far more honest picture of how the system might behave in the future.",
             "callout": "If results collapse on unseen data, the edge was probably noise."},
            {"type": "checklist", "title": "Tips",
             "items": ["Decide the window sizes **before** you look at any results.",
                       "Keep the rules, and the number of parameters, small.",
                       "Judge the combined out-of-sample results, not the best round.",
                       "Expect out-of-sample results to be weaker than in-sample ones."]},
            CTA,
        ],
        "caption": "A trap almost every beginner falls into: tuning a strategy on 5 years of data, then 'testing' it on the same 5 years.\n\n"
                   "Of course it looks good. It was built to fit that exact history.\n\n"
                   "Walk-forward testing fixes this:\n1. Tune the rules on one period\n2. Test them on the next period, which they've never seen\n"
                   "3. Slide forward and repeat\n\n"
                   "Only the unseen test periods count. It's the closest thing to live trading you can do with historical data.\n\n"
                   "Do you test your strategies out-of-sample?",
        "hashtags": ["#backtesting", "#algotrading", "#systematictrading", "#quanttrading", "#tradingstrategy"],
    })

    P.append({
        "id": "20-fomo", "pillar": "Psychology", "label": "Lesson 20 · Psychology",
        "slides": [
            {"type": "cover", "kicker": "Trading psychology", "title": "The trade you **missed** cost you exactly ₹0.",
             "sub": "The one you chased might cost a lot more."},
            {"type": "text", "title": "What FOMO does",
             "body": "- You see a big move you're not part of.\n- You jump in late, far from any sensible stop.\n"
                     "- The move pauses or reverses, and you exit at a loss.\n"
                     "Chasing turns a missed opportunity into a real loss.",
             "callout": "Missing a move is free. Chasing one is not."},
            {"type": "checklist", "title": "Before you chase, ask",
             "items": ["Is this a setup my rules allow, or just a move I saw?",
                       "Where's my stop, and is the risk still sensible from here?",
                       "Would I take this trade if I hadn't watched it rally?",
                       "Can I wait for the next valid setup instead?"]},
            {"type": "text", "title": "There's always another trade",
             "body": "Markets offer new setups every day. Your job isn't to catch every move, but to take the ones your rules "
                     "define, with a known risk.\nMissing trades is part of every system. Chasing them is part of none.",
             "callout": "Discipline means being okay with missing out."},
            CTA,
        ],
        "caption": "The market runs without you. Your feed is full of profit screenshots. You jump in.\n\n"
                   "That's FOMO, and it tends to buy near the top.\n\nWhen you chase a move:\n"
                   "→ You enter late, with the stop far away or missing\n→ You take a setup your rules never approved\n"
                   "→ You're the last buyer before the pullback\n\n"
                   "A missed trade costs ₹0. A chased trade can cost a lot. There's always another setup tomorrow.\n\n"
                   "Save this for the next time a move makes you feel left behind.",
        "hashtags": ["#tradingpsychology", "#fomo", "#tradingdiscipline", "#tradingmindset", "#stockmarketindia"],
    })

    xs, naked, fly = straddle_vs_fly()
    P.append({
        "id": "21-hedged-vs-naked", "pillar": "Options", "label": "Lesson 21 · Options",
        "slides": [
            {"type": "cover", "kicker": "Option selling",
             "title": "Selling options without a hedge means **unlimited** risk.",
             "sub": "How buying 'wings' caps the worst case."},
            {"type": "chart", "title": "Short straddle vs iron fly",
             "body": "Illustrative: sell the 100 call and put for 8 in total; buy the 90 put and 110 call for 2.",
             "chart": {"kind": "line", "title": "Profit or loss per unit at expiry", "x": xs,
                       "series": [{"name": "Hedged (iron fly)", "values": fly, "focus": True},
                                  {"name": "Naked (short straddle)", "values": naked}],
                       "area": False, "zero_line": True, "y_format": "{:g}", "y_ticks": [-15, -10, -5, 0, 5],
                       "x_label": "Price at expiry", "x_ticks": [75, 85, 95, 105, 115, 125], "end_dots": False,
                       "points": [{"series": 0, "x": 118, "label": "Max loss −4", "dx": -80, "dy": 22},
                                  {"series": 1, "x": 80, "label": "No floor", "dx": 20, "dy": -12}]},
             "note": "Illustrative prices. Ignores costs and margin."},
            {"type": "compare", "title": "What the hedge changes",
             "cards": [{"name": "Naked", "rows": [["Premium collected", "8"], ["Max profit", "8"],
                                                  ["Max loss", "Unlimited"]],
                        "result": "No floor", "result_label": "Worst case", "pill": "Open-ended risk", "good": False},
                       {"name": "Hedged", "rows": [["Net premium", "6"], ["Max profit", "6"], ["Max loss", "4"]],
                        "result": "Capped at 4", "result_label": "Worst case", "pill": "Defined risk", "good": True}],
             "body": "You give up some premium (8 becomes 6) in exchange for a known worst case."},
            {"type": "checklist", "title": "Why defined risk matters",
             "items": ["Gap moves happen, and a naked position has no floor.",
                       "In India, hedged positions usually need much less **margin**.",
                       "A known maximum loss lets you size positions properly.",
                       "The hedge costs premium: that's the price of survival."]},
            CTA,
        ],
        "caption": "Option sellers win often. But without a hedge, one bad day can wipe out months.\n\n"
                   "Sell a call and a put at 100 (a short straddle) for a total premium of 8, and your profit is capped at 8, while your "
                   "loss has no limit if the market gaps hard either way.\n\n"
                   "Now buy a 90 put and a 110 call for 2 (turning it into an iron fly). You keep less premium (6), but your worst case "
                   "is capped at 4.\n\n"
                   "That's the trade-off: a little less income for a known, survivable worst case. In India, hedged positions usually "
                   "need much less margin too.\n\n(Illustrative numbers. Not a recommendation.)",
        "hashtags": ["#optionselling", "#optionstrading", "#hedging", "#riskmanagement", "#stockmarketindia"],
    })

    P.append({
        "id": "22-position-size-formula", "pillar": "Risk", "label": "Lesson 22 · Risk",
        "slides": [
            {"type": "cover", "kicker": "Position sizing",
             "title": "How many shares should you buy? Your **stop-loss** decides.",
             "sub": "The position-size formula in one slide."},
            {"type": "formula", "title": "The formula",
             "formula": "Position size =\n(Capital × Risk %) ÷ (Entry − Stop)",
             "body": "- **Capital × Risk %** = the most you'll lose if the stop is hit\n"
                     "- **Entry − Stop** = what you lose per share\n"
                     "- Divide one by the other = how many shares to buy"},
            {"type": "text", "title": "Worked example",
             "body": "Illustrative numbers:\n- Capital ₹10,00,000, risking 1% = **₹10,000**\n"
                     "- Entry ₹500, stop ₹480 = **₹20** risk per share\n"
                     "- Size = 10,000 ÷ 20 = **500 shares** (a ₹2,50,000 position)\n"
                     "If the stop is hit, you lose about ₹10,000 (plus costs and any slippage): exactly the 1% you planned."},
            {"type": "text", "title": "Tight stop vs wide stop",
             "body": "- Stop ₹10 away: 1,000 shares\n- Stop ₹20 away: 500 shares\n- Stop ₹50 away: 200 shares\n"
                     "The risk is ₹10,000 every time. A wider stop means a **smaller** position, not a bigger risk.",
             "callout": "Pick the stop first. The size comes from the stop, never the other way round."},
            CTA,
        ],
        "caption": "Most traders pick a position size by feel: \"I'll buy 500 shares.\" Professionals work it out backwards from the stop-loss.\n\n"
                   "Position size = (capital × risk %) ÷ (entry − stop)\n\n"
                   "Example: ₹10,00,000 capital, 1% risk = ₹10,000. Entry ₹500, stop ₹480, so ₹20 risk per share. "
                   "Position: 10,000 ÷ 20 = 500 shares.\n\n"
                   "If the stop is hit, you lose about ₹10,000, exactly what you planned (plus costs).\n\n"
                   "A wider stop means fewer shares; a tighter stop means more. Your risk stays the same.\n\n(Illustrative numbers.)",
        "hashtags": ["#positionsizing", "#riskmanagement", "#stoploss", "#tradingeducation", "#stockmarketindia"],
    })

    P.append({
        "id": "23-backtest-biases", "pillar": "Systems", "label": "Lesson 23 · Systems",
        "slides": [
            {"type": "cover", "kicker": "Backtesting traps",
             "title": "Two silent bugs that make backtests look **better** than reality.",
             "sub": "Look-ahead bias and survivorship bias."},
            {"type": "text", "title": "1. Look-ahead bias",
             "body": "Using information in the test that you **couldn't have known** at the time. For example:\n"
                     "- Buying at today's open using today's closing price\n"
                     "- Using results that were only published weeks later\n"
                     "- Choosing settings after seeing the whole period",
             "callout": "If you couldn't have known it at the time, your test can't use it."},
            {"type": "text", "title": "2. Survivorship bias",
             "body": "Testing only on stocks that **still exist today**.\n"
                     "Companies that went bankrupt, merged or were removed from an index vanish from many datasets. "
                     "Leaving them out makes almost any strategy look better than it really was.",
             "callout": "Test on the list as it was **then**, not as it is now."},
            {"type": "checklist", "title": "Quick audit",
             "items": ["Every signal uses only data available **before** the trade.",
                       "Orders fill at a realistic price and time, with costs included.",
                       "The universe includes delisted and removed stocks.",
                       "Results were checked on a period you didn't tune on."]},
            CTA,
        ],
        "caption": "Your backtest might be lying to you, and not because of the strategy.\n\nTwo classic bugs:\n\n"
                   "1. Look-ahead bias: the test uses information you couldn't have known at the time, like trading at the open "
                   "using that day's close.\n\n"
                   "2. Survivorship bias: testing only on stocks that exist today. The ones that went bust or were dropped from the "
                   "index vanish from the data, and results look better than they ever were.\n\n"
                   "Both inflate returns, and both are easy to miss. Run the quick audit on the slides before you trust any backtest.",
        "hashtags": ["#backtesting", "#algotrading", "#quanttrading", "#systematictrading", "#tradingeducation"],
    })

    xs, ys, (t1, d1), (t2, d2) = corrections_path()
    P.append({
        "id": "24-corrections-bear-markets", "pillar": "Fundamentals", "label": "Lesson 24 · Fundamentals",
        "slides": [
            {"type": "cover", "kicker": "Market basics",
             "title": "Correction, bear market, crash: what's the **difference**?",
             "sub": "The common definitions, measured from the peak."},
            {"type": "chart", "title": "Measured from the last peak",
             "body": "Two falls on an illustrative index.",
             "chart": {"kind": "line", "title": "Index level", "x": xs,
                       "series": [{"name": "Index", "values": ys, "focus": True}],
                       "y_format": "{:.0f}", "x_ticks": [], "end_dots": False, "area_base": 90,
                       "y_ticks": [90, 100, 110, 120, 130, 140],
                       "points": [{"x": t1, "label": f"Correction {d1:.0f}%", "dx": 16, "dy": 22},
                                  {"x": t2, "label": f"Bear market {d2:.0f}%", "dx": 16, "dy": 22}]},
             "note": "Synthetic data for illustration, not a real index."},
            {"type": "text", "title": "The usual definitions",
             "body": "Measured from the most recent peak:\n- **Pullback:** a fall of up to about 10%\n"
                     "- **Correction:** a fall of 10% to 20%\n- **Bear market:** a fall of 20% or more\n"
                     "- **Crash:** a very sharp fall in a short time (days or weeks)\n"
                     "These are conventions, not official rules."},
            {"type": "checklist", "title": "What it means for you",
             "items": ["Falls of 10% or more happen regularly in stock markets. Plan for them.",
                       "Know how big a fall your portfolio, and your nerves, can handle.",
                       "Size positions so a correction never forces you to sell.",
                       "Write your rules for a falling market **before** one arrives."]},
            CTA,
        ],
        "caption": "\"Markets are crashing!\" Are they? Or is it just a correction?\n\n"
                   "Common definitions, measured from the most recent peak:\n→ Pullback: down less than about 10%\n"
                   "→ Correction: down 10–20%\n→ Bear market: down 20% or more\n→ Crash: a very sharp fall in days or weeks\n\n"
                   "These are conventions, not official rules, but they help you keep perspective. Falls of 10% or more happen "
                   "regularly in stock markets. Having your plan written before one arrives is what separates calm investors from panic sellers.",
        "hashtags": ["#stockmarketindia", "#bearmarket", "#investingbasics", "#riskmanagement", "#nifty50"],
    })

    ivs, prices = iv_curve()
    p15 = prices[ivs.index(15)]
    p30 = prices[ivs.index(30)]
    P.append({
        "id": "25-implied-volatility", "pillar": "Options", "label": "Lesson 25 · Options",
        "slides": [
            {"type": "cover", "kicker": "Options basics",
             "title": "Why the same option can cost **twice as much** on a different day.",
             "sub": "Meet implied volatility (IV)."},
            {"type": "chart", "title": "Option price vs implied volatility",
             "body": f"Double the IV and the premium roughly doubles: {p15:.2f} at 15%, {p30:.2f} at 30%.",
             "chart": {"kind": "line", "title": "At-the-money call price, 30 days to expiry", "x": ivs,
                       "series": [{"name": "Call price", "values": prices, "focus": True}],
                       "y_format": "{:.0f}", "y_ticks": [0, 1, 2, 3, 4, 5], "x_format": "{:.0f}%",
                       "x_ticks": [10, 15, 20, 25, 30, 35, 40], "x_label": "Implied volatility", "end_dots": False,
                       "points": [{"x": 15, "label": f"IV 15%: {p15:.2f}", "dx": 20, "dy": -64},
                                  {"x": 30, "label": f"IV 30%: {p30:.2f}", "dx": 20, "dy": -64}]},
             "note": "Black-Scholes model: price 100, strike 100, 30 days, zero interest. Illustrative."},
            {"type": "text", "title": "What IV means",
             "body": "Implied volatility is the size of move the market is **pricing in**, worked backwards from option prices.\n"
                     "- Higher IV means bigger expected swings and pricier options\n"
                     "- Lower IV means smaller expected swings and cheaper options\n"
                     "IV often rises before big events (results, elections, budgets) and drops after them."},
            {"type": "checklist", "title": "Why traders watch it",
             "items": ["Buying when IV is high means paying up for the move.",
                       "After an event, IV often drops (an 'IV crush'), and premiums fall even if the price moves your way.",
                       "Sellers collect more when IV is high, but face bigger expected moves.",
                       "Compare today's IV with its usual range, not in isolation."]},
            CTA,
        ],
        "caption": "Same underlying, same strike, same days to expiry, and the option costs twice as much. Why?\n\n"
                   "Implied volatility (IV): the size of move the market is pricing in.\n\n"
                   f"In the Black-Scholes example (price 100, strike 100, 30 days), an at-the-money call costs about {p15:.1f} at 15% IV "
                   f"and about {p30:.1f} at 30% IV. Double the IV, roughly double the premium.\n\n"
                   "IV tends to rise before big events like results or elections, and drop sharply after. That drop can shrink an "
                   "option's price even when you got the direction right.\n\nAlways check IV before you trade an option.",
        "hashtags": ["#optionstrading", "#impliedvolatility", "#optionsbasics", "#tradingeducation", "#stockmarketindia"],
    })

    # Hand-designed candles (open, high, low, close): a range with a floor at 100 that holds three times.
    candles = [[104.0, 104.6, 103.2, 103.4], [103.4, 103.7, 102.1, 102.3], [102.3, 102.6, 100.9, 101.1],
               [101.1, 101.4, 100.2, 100.6], [100.6, 102.0, 100.4, 101.8], [101.8, 103.4, 101.5, 103.1],
               [103.1, 104.8, 102.8, 104.5], [104.5, 106.2, 104.2, 105.8], [105.8, 106.4, 104.6, 104.9],
               [104.9, 105.1, 103.2, 103.4], [103.4, 103.8, 101.6, 101.9], [101.9, 102.2, 100.3, 100.7],
               [100.7, 102.3, 100.5, 102.0], [102.0, 103.9, 101.7, 103.6], [103.6, 105.3, 103.3, 104.9],
               [104.9, 105.2, 103.6, 103.8], [103.8, 104.0, 102.0, 102.3], [102.3, 102.5, 100.8, 101.0],
               [101.0, 101.3, 100.25, 100.5], [100.5, 102.1, 100.35, 101.9]]
    P.append({
        "id": "26-stop-placement", "pillar": "Risk", "label": "Lesson 26 · Risk",
        "slides": [
            {"type": "cover", "kicker": "Stop-losses",
             "title": "Put your stop where your idea is **wrong**, not where the pain starts.",
             "sub": "A logical stop vs a random one."},
            {"type": "chart", "title": "Stop below the level that proves you wrong",
             "body": "Illustrative chart: price has bounced off the same floor three times.",
             "chart": {"kind": "candles", "ohlc": candles,
                       "levels": [{"y": 101.9, "label": "Entry"}, {"y": 100.9, "label": "Stop in the noise"},
                                  {"y": 100.0, "label": "Floor"}, {"y": 99.2, "label": "Logical stop", "focus": True}]},
             "note": "Synthetic chart for illustration, not real market data."},
            {"type": "text", "title": "Two ways to set a stop",
             "body": "- **Pain-based:** \"I'll get out if I'm down ₹5,000.\" The market doesn't know your number, so the stop sits in random noise.\n"
                     "- **Logic-based:** \"If price breaks below this floor, my reason for the trade is gone.\" The stop sits where the idea is disproved.\n"
                     "Then size the position so that stop equals your planned risk.",
             "callout": "Stop first, then size. Never the other way round."},
            {"type": "checklist", "title": "Stop-loss rules of thumb",
             "items": ["Leave a little room below the level for normal noise.",
                       "Never move a stop further away once you're in.",
                       "If the logical stop is too far for your risk, **skip the trade** or trade smaller.",
                       "Use a stop-loss order, or an alert you always act on."]},
            CTA,
        ],
        "caption": "Where do you put your stop-loss? If the answer is \"wherever it starts to hurt\", read on.\n\n"
                   "A stop based on pain (\"I'll exit at −₹5,000\") sits at a random spot the market doesn't care about. It gets hit by "
                   "normal noise, and then price carries on in your direction without you.\n\n"
                   "A logical stop sits where your trade idea is proven wrong: for example, just below a floor that price has respected. "
                   "If that level breaks, the reason for the trade is gone.\n\n"
                   "Pick the logical stop first. Then size your position so that stop equals the risk you planned.",
        "hashtags": ["#stoploss", "#riskmanagement", "#technicalanalysis", "#tradingeducation", "#stockmarketindia"],
    })

    cats, vals = mc_reshuffle()
    P.append({
        "id": "27-monte-carlo-drawdown", "pillar": "Systems", "label": "Lesson 27 · Systems",
        "slides": [
            {"type": "cover", "kicker": "Monte Carlo",
             "title": "Same 100 trades, same profit, and a drawdown anywhere from **4R to 26R**.",
             "sub": "Your backtest's drawdown is just one roll of the dice."},
            {"type": "chart", "title": "One set of trades, 20,000 orders",
             "body": "45 wins of +1.5R and 55 losses of −1R, shuffled. Every order ends at +12.5R.",
             "chart": {"kind": "bar", "title": "Share of orders with this worst drawdown", "categories": cats,
                       "values": vals, "value_format": "{:.0f}%", "highlight": [5, 6, 7],
                       "x_label": "Worst drawdown (R)"},
             "note": "Simulation, not real trades. R = amount risked per trade."},
            {"type": "text", "title": "What this tells you",
             "body": "**R** is the amount you risk on each trade.\n"
                     "- Every shuffle ends with the **same** +12.5R profit.\n"
                     "- But the worst drawdown ranges from 4R to 26R.\n"
                     "- In 1 order out of 20, it's 14.5R or deeper, with identical trades.\n"
                     "The order of wins and losses is luck. Your backtest showed you just one order.",
             "callout": "Plan for the bad-luck drawdown, not the one in your backtest."},
            {"type": "checklist", "title": "How to use this",
             "items": ["Shuffle your backtest trades (Monte Carlo) to see the range of drawdowns.",
                       "Size positions for the bad-luck drawdown, not the historical one.",
                       "Set a 'system is broken' limit beyond that worst case.",
                       "Expect live drawdowns to be deeper than the backtest's."]},
            CTA,
        ],
        "caption": "Your backtest says the worst drawdown was 9R. Should you plan for 9R?\n\n"
                   "We took 100 trades (45 wins of +1.5R, 55 losses of −1R) and shuffled their order 20,000 times. Every version ends "
                   "with exactly the same profit: +12.5R.\n\n"
                   "But the worst drawdown ranged from 4R to 26R. One order in 20 hit 14.5R or worse.\n\n"
                   "The order of wins and losses is luck, and your backtest shows you just one order. Size for the bad-luck version, "
                   "not the lucky one.\n\n(R = amount risked per trade. Simulation, not real trades.)",
        "hashtags": ["#montecarlo", "#backtesting", "#riskmanagement", "#systematictrading", "#quanttrading"],
    })

    P.append({
        "id": "28-buyer-vs-seller", "pillar": "Options", "label": "Lesson 28 · Options",
        "slides": [
            {"type": "cover", "kicker": "Options basics",
             "title": "Option buyers and sellers are paid for **different** things.",
             "sub": "Neither side gets a free lunch."},
            {"type": "compare", "title": "Two sides of every option",
             "cards": [{"name": "Buyer", "rows": [["Premium", "Pays it upfront"], ["Max loss", "Premium paid"],
                                                  ["Max gain", "Large"]],
                        "result": "Wins less often", "result_label": "Typically", "pill": "Pays for time",
                        "good": False, "neutral": True},
                       {"name": "Seller", "rows": [["Premium", "Receives it upfront"], ["Max gain", "Premium received"],
                                                   ["Max loss", "Large, unless hedged"]],
                        "result": "Wins more often", "result_label": "Typically", "pill": "Paid to take risk",
                        "good": False, "neutral": True}],
             "body": "High win rate or big payoff: every option trade is a trade-off between the two."},
            {"type": "text", "title": "The trade-off",
             "body": "- **Buyers** risk a small, known amount for a chance at a big move. They often lose small, but can occasionally win big.\n"
                     "- **Sellers** collect small premiums often, but one large move can cost many times the premium.\n"
                     "Neither side wins by default. The edge comes from pricing, sizing and risk control."},
            {"type": "checklist", "title": "Questions to ask before either",
             "items": ["What's my maximum loss, in rupees?", "How many days to expiry, and is time on my side?",
                       "Is implied volatility high or low right now?", "If I'm selling, where's my hedge?"]},
            CTA,
        ],
        "caption": "Option buyers dream of 10x. Option sellers love their high win rates. Both can go broke.\n\n"
                   "Buyers pay a premium for the chance of a big move. Their risk is limited to what they paid, but time works against "
                   "them and many trades lose small.\n\n"
                   "Sellers collect premium and are right more often. But their gain is capped at the premium, and an unhedged position "
                   "can lose many times that on one big move.\n\n"
                   "Neither side is 'better'. The edge comes from how options are priced, how big you trade and how you control risk.\n\n"
                   "Which side do you usually trade?",
        "hashtags": ["#optionstrading", "#optionselling", "#optionbuying", "#tradingeducation", "#stockmarketindia"],
    })

    rcats, med, p95 = mc_risk()
    P.append({
        "id": "29-drawdown-vs-risk", "pillar": "Risk", "label": "Lesson 29 · Risk",
        "slides": [
            {"type": "cover", "kicker": "Monte Carlo",
             "title": "Risk **2%** per trade instead of 1%, and your typical drawdown roughly **doubles**.",
             "sub": "20,000 simulations of the same strategy."},
            {"type": "chart", "title": "Typical worst drawdown",
             "body": "Median worst drawdown over 200 trades, by risk per trade.",
             "chart": {"kind": "bar", "title": "Median max drawdown", "categories": rcats, "values": med,
                       "value_format": "{:.0f}%", "highlight": [1], "x_label": "Risk per trade"},
             "note": "Simulation: 45% win rate, winners 1.5× losers, 200 trades, 20,000 runs."},
            {"type": "chart", "title": "The unlucky runs",
             "body": "The drawdown that 1 run in 20 reached or exceeded.",
             "chart": {"kind": "bar", "title": "Bad-luck max drawdown (95th percentile)", "categories": rcats,
                       "values": p95, "value_format": "{:.0f}%", "highlight": [1], "x_label": "Risk per trade"},
             "note": "Same simulation as the previous slide."},
            {"type": "text", "title": "Bigger bets, deeper holes",
             "body": "Same strategy, same edge. The only change is size.\n"
                     "- The typical result grows faster with more risk...\n"
                     "- ...but so does the drawdown, and so does the chance of finishing **below** where you started.\n"
                     "At 5% risk, 1 run in 20 finished down 39% or more after 200 trades.",
             "callout": "Choose your risk per trade by the drawdown you can live with."},
            CTA,
        ],
        "caption": "Want to grow faster? Just risk more per trade, right?\n\n"
                   "We simulated one strategy (45% win rate, winners 1.5× the size of losers) for 200 trades, 20,000 times, at "
                   "different risk levels. Typical worst drawdown:\n"
                   f"→ 0.5% risk: ~{med[0]:.0f}%\n→ 1% risk: ~{med[1]:.0f}%\n→ 2% risk: ~{med[2]:.0f}%\n→ 5% risk: ~{med[4]:.0f}%\n\n"
                   f"In the unlucky 1-in-20 runs, 5% risk meant a drawdown of {p95[4]:.0f}%.\n\n"
                   "Bigger size only speeds up growth if you survive the drawdowns. Pick your risk per trade from the drawdown you "
                   "can actually live with, emotionally and financially.\n\n(Simulation, not real results.)",
        "hashtags": ["#riskmanagement", "#positionsizing", "#montecarlo", "#systematictrading", "#tradingeducation"],
    })

    P.append({
        "id": "30-trading-journal", "pillar": "Systems", "label": "Lesson 30 · Systems",
        "slides": [
            {"type": "cover", "kicker": "Trading journal", "title": "If you don't **write it down**, you can't improve it.",
             "sub": "The 8 things worth logging on every trade."},
            {"type": "checklist", "title": "Log these for every trade",
             "items": ["Date, instrument and setup name", "Entry, stop and target, **planned** before entry",
                       "Position size and rupee risk", "Exit price and the reason you exited",
                       "Result in rupees and in R", "Did I follow my rules? (yes / no)",
                       "How I felt before and during the trade", "One lesson for next time"]},
            {"type": "text", "title": "What a journal reveals",
             "body": "After 50 to 100 entries, patterns appear:\n- Which setups actually make money\n"
                     "- What time of day you trade best (and worst)\n"
                     "- How often you break your own rules, and what it costs\n"
                     "- Whether your losses come from the system or from you",
             "callout": "A backtest tests your strategy. A journal tests **you**."},
            CTA,
        ],
        "caption": "The fastest way to become a better trader isn't a new indicator. It's a notebook.\n\n"
                   "Log every trade: setup, planned entry, stop and target, size, exit reason, result in rupees and in R, whether "
                   "you followed your rules, and how you felt.\n\n"
                   "After 50–100 trades, the journal starts talking. You'll see which setups really pay, when you trade badly, and how "
                   "much breaking your own rules is costing you.\n\n"
                   "A backtest tests your strategy. A journal tests you.\n\nDo you keep a trading journal? Excel, app or notebook?",
        "hashtags": ["#tradingjournal", "#tradingdiscipline", "#tradingpsychology", "#systematictrading", "#stockmarketindia"],
    })

    P.append({
        "id": "31-option-greeks", "pillar": "Options", "label": "Lesson 31 · Options",
        "slides": [
            {"type": "cover", "kicker": "Options basics", "title": "The option **Greeks**, in plain English.",
             "sub": "Four letters that explain why your option's price moves."},
            {"type": "checklist", "title": "The big four",
             "items": ["**Delta:** how much the option moves when the underlying moves by 1.",
                       "**Gamma:** how fast delta itself changes. Highest near the strike and near expiry.",
                       "**Theta:** how much value the option loses each day to time decay.",
                       "**Vega:** how much the option moves when implied volatility changes by 1 point."]},
            {"type": "text", "title": "A quick example",
             "body": "An illustrative call with delta 0.50, theta −2 and vega 1.5:\n"
                     "- Underlying up 10: option up about **5** (0.50 × 10)\n"
                     "- One day passes: option down about **2**\n"
                     "- IV up 2 points: option up about **3** (1.5 × 2)\n"
                     "They all act at once, so the net move is roughly the sum.",
             "callout": "Greeks are estimates. They change as price, time and IV change."},
            {"type": "checklist", "title": "Who watches which Greek",
             "items": ["Buyers: delta (direction) and theta (the daily cost).",
                       "Sellers: theta (the income) and gamma (the danger near expiry).",
                       "Everyone: vega around big events like results and elections."]},
            CTA,
        ],
        "caption": "Why did your call lose money when the market went up? The Greeks can tell you.\n\n"
                   "→ Delta: how much the option moves for a 1-point move in the underlying\n"
                   "→ Gamma: how fast delta changes (biggest near the strike and near expiry)\n"
                   "→ Theta: the value lost each day to time decay\n"
                   "→ Vega: the change in price for a 1-point change in implied volatility\n\n"
                   "They all act at the same time. A small price gain can be wiped out by theta or a drop in IV.\n\n"
                   "Save this cheat sheet for the next time an option price surprises you.",
        "hashtags": ["#optionsgreeks", "#optionstrading", "#optionsbasics", "#tradingeducation", "#stockmarketindia"],
    })

    P.append({
        "id": "32-pre-trade-checklist", "pillar": "Systems", "label": "Lesson 32 · Systems",
        "slides": [
            {"type": "cover", "kicker": "Discipline",
             "title": "Pilots run a checklist before every flight. **Traders should too.**",
             "sub": "A 6-point pre-trade checklist."},
            {"type": "checklist", "title": "Before every trade",
             "items": ["Is this a setup my written rules allow?", "Where's my stop, and why there?",
                       "Is my size worked out from that stop and my risk %?",
                       "Have I checked costs, events and the expiry date?", "Am I within my daily loss limit?",
                       "Am I calm, or trading to feel something?"]},
            {"type": "text", "title": "Why checklists work",
             "body": "Most costly mistakes aren't about knowledge. They're skipped steps: no stop, the wrong size, a trade "
                     "right before a big event.\nA checklist forces a pause between the impulse and the order. That pause is "
                     "where discipline lives.",
             "callout": "If any answer is 'no', there's no trade."},
            CTA,
        ],
        "caption": "Airline pilots have thousands of hours of experience, and they still run a checklist before every take-off. "
                   "Under pressure, anyone skips steps.\n\n"
                   "Trading is the same. The worst trades usually aren't bad ideas; they're good ideas executed badly: no stop, the "
                   "wrong size, a trade right before a big announcement, or a trade taken out of boredom.\n\n"
                   "Use the 6-point checklist on the slides before every order. If any answer is 'no', the trade doesn't happen.\n\n"
                   "Save it, and keep it next to your screen.",
        "hashtags": ["#tradingdiscipline", "#tradingpsychology", "#systematictrading", "#riskmanagement", "#tradingeducation"],
    })
    return P


if __name__ == "__main__":
    lib = {"version": 1, "posts": posts()}
    with open(os.path.join(HERE, "library.json"), "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print(f"Wrote {len(lib['posts'])} posts")
