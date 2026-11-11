# SlotSense — floor intelligence for VelocityMart

Most slotting tools rank SKUs by velocity and tell you to move fast movers closer to dispatch.
SlotSense starts from a different question: **which products are being handled, right now, from a
slot that breaks a rule — and what is the smallest set of moves that fixes the most risk?**

On the bundled VelocityMart data that question has a sharp answer: only **33% of SKUs sit in a
compliant slot**, and the planner finds a valid empty slot for 535 of the 539 offenders.

## What it does

| View | What you get |
| :-- | :-- |
| **Floor map** | Side elevation of the building (150 aisles × 6 shelf levels) coloured by risk exposure, rule breaks, velocity or occupancy. |
| **Move planner** | A work order sized to what a shift can absorb. Moves are ranked by *exposure* (rule severity × picks per week), every target slot is checked against every rule, and a what-if shows compliance before and after. Exports to CSV. |
| **Risk ledger** | Every SKU in a bad slot with the exact rules it breaks, filterable by rule and category. |
| **Shift pressure** | Weekday × hour pick-rate clock, so moves get scheduled outside the peak, plus load on the 1.2 m aisles where two pickers cannot pass. |
| **Picker signals** | Robust outlier detection (median/MAD) on logged travel per pick. It flags one picker logging half the distance of the other eleven — more likely a scanner fault than a shortcut. |

### Rules checked

Wrong temperature zone · over shelf weight limit · slot shared by several SKUs · fragile item on a
top shelf · heavy (≥ 20 kg) item on a top shelf.

### What it deliberately does not claim

The order log's `travel_distance_m` does not vary with where a SKU is stored (it is the same
~33.6 m average for every zone, aisle and shelf level), so SlotSense does **not** promise travel
savings from re-slotting. The plan is justified by compliance and handling risk only.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

```bash
pip install pytest && pytest -q    # 6 tests on the engine, including the real dataset
```

## Layout

```text
app.py        Streamlit UI (blueprint theme in .streamlit/config.toml)
engine.py     All analysis and the move planner — pure pandas, no UI imports
tests/        pytest suite
*.csv         SKU master, 174k order lines, 18k slot definitions
```
