# Functional evaluation

Full workflow: **20 of 20 passed**.

- Intent accuracy: 1.0
- Required-phrase accuracy: 1.0
- Citation accuracy: 1.0
- Mean latency: 11.788 ms

Retrieval-only baseline (RAG subgraph, no router and no calculators),
scored on the same phrases and documents, ignoring intent:

- Passed: 12 of 20
- Required-phrase accuracy: 0.6
- Citation accuracy: 0.85

| ID | Intent | OK | Answer |
| --- | --- | --- | --- |
| q01 | policy_lookup | pass | A single ticket is valid for 90 minutes from the time of purchase. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a penalty not... |
| q02 | policy_lookup | pass | An adult single ticket costs 2.40 EUR in zone 1. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a penalty notice. Station staff... |
| q03 | policy_lookup | pass | Lost property is kept for 30 days. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a penalty notice. Station staff confirm claim... |
| q04 | policy_lookup | pass | A passenger without a valid ticket must pay a penalty fare of 60 EUR. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a penalty ... |
| q05 | policy_lookup | pass | Passenger assistance must be booked at least 2 hours before departure. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a penalty... |
| q06 | policy_lookup | pass | An unused single ticket can be refunded within 14 days of purchase. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a penalty no... |
| q07 | policy_lookup | pass | Podoba Transit keeps an administration fee of 5 EUR on a season ticket refund. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or... |
| q08 | policy_lookup | pass | Podoba Transit sends a first response to a complaint within 5 working days. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a ... |
| q09 | policy_lookup | pass | A final response to a complaint is sent within 20 working days. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a penalty notice... |
| q10 | policy_lookup | pass | Bicycles are not allowed on trains arriving in the city centre between 07:30 and 09:30. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decis... |
| q11 | policy_lookup | pass | PRM means passenger with reduced mobility. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a penalty notice. Station staff confi... |
| q12 | policy_lookup | pass | A single ticket is valid for 90 minutes from the time of purchase. This assistant summarizes Podoba Transit customer rules for information only. It does not create a refund, a compensation decision, or a penalty not... |
| q13 | multi_part | pass | Part 1: A single ticket is valid for 90 minutes from the time of purchase. Part 2: Lost property is kept for 30 days. This assistant summarizes Podoba Transit customer rules for information only. It does not create ... |
| q14 | multi_part | pass | Part 1: An adult single ticket for 2 zones costs 3.60 EUR. An adult single ticket costs 2.40 EUR in zone 1. Each additional zone adds 1.20 EUR. Part 2: Lost property is kept for 30 days. This assistant summarizes Meri... |
| q15 | fare_calc | pass | An adult single ticket for 3 zones costs 4.80 EUR. An adult single ticket costs 2.40 EUR in zone 1. Each additional zone adds 1.20 EUR. This assistant summarizes Podoba Transit customer rules for information only. I... |
| q16 | fare_calc | pass | A child single ticket for 4 zones costs 3.00 EUR. A child single ticket is half the adult single fare for the same number of zones. The adult single fare for 4 zones is 6.00 EUR. This assistant summarizes Podoba Tra... |
| q17 | delay_compensation | pass | The compensation is 4.00 EUR. A delay of 30 to 59 minutes qualifies for compensation of 50 percent of the single ticket price. The ticket price used is 8.00 EUR and the delay used is 45 minutes. This assistant summari... |
| q18 | delay_compensation | pass | The delay does not qualify for compensation. A delay under 30 minutes does not qualify for compensation. The compensation amount is 0.00 EUR. The ticket price used is 6.40 EUR and the delay used is 12 minutes. This as... |
| q19 | chitchat | pass | I am the Podoba Transit customer service assistant. I answer questions about fares, tickets, refunds, delay compensation, accessibility, complaints, lost property, and onboard safety, and I cite the rule I use. |
| q20 | out_of_scope | pass | That question is outside Podoba Transit customer service. I can help with fares, tickets, refunds, delay compensation, accessibility, complaints, lost property, and onboard safety. |
