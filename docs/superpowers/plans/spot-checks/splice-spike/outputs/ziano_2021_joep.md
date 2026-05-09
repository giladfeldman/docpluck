Journal of Economic Psychology 83 (2021) 102350 Contents lists available at ScienceDirect
Journal of Economic Psychology
journal homepage: www.elsevier.com/locate/joep

Replication: Revisiting Tversky and Shafir’s (1992) Disjunction Effect with an extension comparing between and within subject designs
Ignazio Ziano a,1, Man Fai Kong b,1, Hong Joo Kim b,1, Chit Yu Liu b,1, Sze Chai Wong b,1, Bo Ley Cheng b, Gilad Feldman b,*
a Grenoble Ecole de Management, F-38000 Grenoble, France b Department of Psychology, University of Hong Kong, Hong Kong Special Administrative Region

ARTICLE INFO

## Keywords

Disjunction effect Replication Judgment and decision-making Uncertainty Risk Between versus within subject design

## ABSTRACT

Does uncertainty about an outcome influence decisions? The sure-thing principle (Savage, 1954) posits that it should not, but Tversky and Shafir (1992) found that people regularly violate it in hypothetical gambling and vacation decisions, a phenomenon they termed “disjunction effect”. Very close replications and extensions of Tversky and Shafir (1992) were conducted in this paper (N = 890, MTurk). The target article demonstrated the effect using two paradigms in a betweensubject design: here, an extension also testing a within-subject design, with design being randomly assigned was added. These results were consistent with the original findings for the “paying to know“ problem (original: Cramer’s V = 0.22, 95% (CI) [0.14, 0.32]; replication: Cramer’s V = 0.30, 95% CI [0.24, 0.37]), yet not for the “choice under risk” problem (original: Cramer’s V = 0.26, 95% CI [0.14, 0.39]; replication: Cramer’s V = 0.11, 95% CI [− 0.07, 0.20]). The within-subject extension showed very similar results. Implications for the disjunction effect and judgment and decision-making theory are discussed, and a call for improvements on the statistical understanding of comparisons of between-subject and within-subject designs is intro­ duced. All materials, data, and code are available on https://osf.io/gu58m/.

## Introduction

The sure-thing principle (STP; Savage, 1954) is an axiom of rational choice theory. It posits that if decision-makers are willing to make the same decision regardless of whether an external event happens or not, then decision-makers should also be willing to make the same decision when the outcome of the event is uncertain. Tversky and Shafir (1992), however, found that people regularly violate the STP. In a “paying-to-know” paradigm they found that participants were willing to pay a small fee to postpone a decision about a vacation package promotion when outcome of an exam was uncertain, despite preferences to purchase the package regardless of exam outcome. Using a “choice under risk” problem, they found that facing uncertainty about the outcome of an initial bet led to less willingness to again accept the exact same bet, compared to when having learned the outcome of the first bet.
Tversky and Shafir (1992) attributed this effect – coined “disjunction effect” – to the relative ease of coming up with reasons for
* Corresponding author. E-mail addresses: Ignazio.ZIANO@grenoble-em.com (I. Ziano), boleystudies@gmail.com (B.L. Cheng), gfeldman@hku.hk (G. Feldman).
1 Contributed equally, joint first authors.
https://doi.org/10.1016/j.joep.2020.102350 Received 2 April 2020; Received in revised form 24 November 2020; Accepted 17 December 2020 Available online 24 December 2020 0167-4870/© 2020 Elsevier B.V. All rights reserved.

### Table 1
*Descriptive and omnibus inferential statistics, across original studies and replications.*

```
Paying to know
N
Choice
Win
Loss
Uncertain Inferential
Statistics
Tversky & Shafir, 1992,
/
/
/
/
/
/
original (within-
subject)
/
/
/
/
/
/
Tversky & Shafir, 1992, original (betweensubject)
199 Buy (%) 36 (54%)
38 (57%)
21 (32%)
χ2 (4) = 19.02, p < .001
Tversky & Shafir, 1992,
/
modified gambles
(between-subject)
Not buy (%) Pay $5 (%) /
11 (16%) 20 (30%) /
8 (12%) 21 (31%) /
4 (7%)
41 (61%)
/
/
/
/
/
/
/
/
Kühberger et al., 2001,
/
/
/
/
/
/
exp. 1 (between-
subject)
/
/
/
/
/
/
Kühberger et al., 2001,
/
/
/
/
/
/
exp. 2 (between-
subject)
/
/
/
/
/
/
ES [95% CI] / / Cramer’s V = 0.218 [0.137, 0.317]
/
/ / / / /
Kühberger et al., 2001,
/
/
/
/
/
/
/
exp. 3 (within-
subject)
/
/
/
/
/
/
/
Kühberger et al., 2001,
/
/
/
/
/
/
/
exp. 4 (between-
subject)
/
/
/
/
/
/
/
Lambdin & Burdsal, 2007 /
/
/
/
/
/
/
```

### Table 1
*Descriptive and omnibus inferential statistics, across original studies and replications.*

```
Paying to know Choice under risk
N Choice Win Loss Uncertain Inferential ES [95% CI] N Choice Win Loss Uncertain Inferential ES [95% CI]
Statistics Statistics
Tversky & Shafir, 1992, / / / / / / / 98 Accept 68 58 35 (34%)
original (within- (%) (69%) (59%)
subject)
/ / / / / / / Reject 30 40 63 (66%)
(%) (31%) (41%)
Tversky & Shafir, 1992, 199 Buy (%) 36 38 21 (32%) χ2 (4) =19.02, Cramer’s V = 213 Accept 49 40 χ2 (2) =13.89, Cramer’s V
original (between- (54%) (57%) p <.001 0.218 [0.137, (%) (69%)1 (57%)1 p <.001 =0.255
subject) 0.317] [0.144,
0.394]
Not buy 11 8 4 (7%) Reject 22 31
(%) (16%) (12%) (%) (31%)1 (43%)1
Pay $5 20 21 41 (61%)
(%) (30%) (31%)
Tversky & Shafir, 1992, / / / / / / / 171 Accept 42 39 43 χ2 (2) =0.76, Cramer’s V
modified gambles (%) (73%)1 (69%)1 (75%)1 p =.68 =0.067
(between-subject) [(cid:0) 0.108,
0.218]
/ / / / / / / Reject 15 18 14
(%) (27%)1 (31%)1 (25%)1
Kühberger et al., 2001, / / / / / / / 177 Accept … …
exp. 1 (between- (%) (60%)2 (47%)2 (47%)2
subject)
/ / / / / / / Reject … …
(%) (40%)2 (53%)2 (53%)2
Kühberger et al., 2001, / / / / / / / 184 Accept … …
exp. 2 (between- (%) (83%)2 (70%)2 (62%)2
subject)
/ / / / / / / Reject … …
(%) (17%)2 (30%)2 (38%)2
Kühberger et al., 2001, / / / / / / / 35 Accept 28 13 15 … …
exp. 3 (within- (%) (80%)1 (37%)1 (43%)1
subject)
/ / / / / / / Reject 7 22 20 … …
(%) (20%)1 (63%)1 (57%)1
Kühberger et al., 2001, / / / / / / / 97 Accept … …
exp. 4 (between- (%) (68%)2 (32%)2 (38%)2
subject)
/ / / / / / / Reject … …
(%) (32%)2 (68%)2 (62%)2
Lambdin & Burdsal, 2007 / / / / / / / 55 Accept 35 26 21 (38%) … …
(within-subject) (%) (64%) (47%)
/ / / / / / / Reject 20
```

```
†
(continued on next page)
Table 1 (continued )
Paying to know
N
Choice
Win
Loss
Present work (betweensubject)
Not buy 97
(%)
(22%)
Pay $5 92
(%)
(21%)
445 Buy (%) 58
(39%)
247 (56%) 71 (16%) 61 (42%)
Not buy (%) Pay $5 (%)
38 (26%) 52 (35%)
61 (42%) 22 (16%)
```

1Reconstructed cell Ns. 2Impossible to recover cell N because no cell size is specified. †No appropriate omnibus effect size. /Absent. - - -Impossible to calculate without original data.

```
Uncertain
168 (38%) 178 (40%) 25 (16%)
Inferential Statistics Friedman χ2 (2) = 132.678, p < .001
χ2 (4) = 81.00, p < .001
ES [95% CI]
Cramer’s V = 0.302 [0.239, 0.368]
29 (19%)
99 (65%)
Choice under risk
N
Choice
Win
Reject (%)
281 (63%)
Loss
258 (58%)
Uncertain
280 (63%)
Inferential Statistics
Cochran’s Q (2) = 4.63, p = .099
ES [95% CI]
445 Accept (%)
46 (31%)
56 (38%)
65 (44%)
Reject (%)
102 (69%)
92 (62%)
84 (56%)
χ2 (2) = 4.99, p = .082
Cramer’s V = 0.106 [− 0.067, 0.202]
```

### Table 2
*Comparison of differences across conditions.*

```
Paying to know, , difference in % Pay $5 across conditions
N
Pass-Fail
Pass-Uncertain
Fail-Uncertain
```

Tversky & Shafir, 1992 (within-subjects)
Inferential statistics Effect size [95% CI] Tversky & Shafir, 1992
(between-subjects) Inferential statistics
Effect size [95% CI]
Tversky & Shafir, 1992, modified gambles (between-subjects)
Inferential statistics

```
/
/
/
/
/
/
/
/
/
199 − 1
− 31
χ2 (2) = 0.552, p = .759
χ2 (2) = 14.437, p < .001
Cramer’s V = Cramer’s V =
[− 0.122,
[0.188, 0.505]
0.231]
/
/
/
```

/
/ / − 30
χ2 (2) = 12.676, p = .001 Cramer’s V = 0.308 [0.171, 0.484]
/

```
/
/
/
/
Effect size [95% CI]
/
/
/
/
Kühberger et al., 2001, exp. 1 /
/
/
(between-subject)
Inferential statistics
/
/
/
Effect size [95% CI]
/
/
/
Kühberger et al., 2001, exp. 2 /
/
/
(between-subject)
Inferential statistics
/
/
/
Effect size [95% CI]
/
/
/
Kühberger et al., 2001, exp. 3 /
/
/
(within-subject)
Inferential statistics
/
/
/
Effect size [95% CI]
/
/
/
Kühberger et al., 2001, exp. 4 /
/
/
(between-subject)
Inferential statistics
/
/
/
```

Effect size [95% CI] Lambdin & Burdsal, 2007
(within-subject) Inferential statistics Effect size [95% CI] Present work
(within-subject) Inferential statistics
Effect size [95% CI] Present work
(between-subject) Inferential statistics
Effect size [95% CI]

```
/
/
/
35 17
445 − 5
− 19
χ2 (3) = 138.38, p < .001 †
445 − 20
χ2 (3) = 152.08, p < .001
† − 30
χ2 (2) = 17.53, p < .001 Cramer’s V = 0.245 [0.146, 0.363]
χ2 (2) = 28.88, p < .001 Cramer’s V = 0.31 [0.207, 0.426]
```

/
/
/ /
/
/ /
/ / /
/
/ 9
… … − 24
χ2 (3) = 85.72, p < .001
† − 50
χ2 (2) = 75.24, p < .001 Cramer’s V = 0.503 [0.394, 0.619]

†No appropriate omnibus effect size. /Absent. - - - Impossible to recalculate from original paper.

```
Choice under risk, difference in % Accept across conditions
N
Win-Loss
Win-: Uncertain
LossUncertain
98 10
†
†
213 14
χ2 (1) = 1.927, χ2 (1) =
p = .165
12.484, p <
.001
Cramer’s V = Cramer’s V =
[− 0.083,
[0.168, 0.482]
0.307]
171 − 2
```

… † 17
χ2 (1) = 4.07, p = .04
Cramer’s V = 0.183 [0.08, 0.357]
−4

```
χ2 (1) = 0.171, χ2 (1) < 0.001, χ2 (1) =
p = .68
p > .99
0.391,
p = .531
Cramer’s V = Cramer’s V = Cramer’s V =
[− 0.094,
[− 0.093,
[− 0.094,
0.258]
0.207]
0.278]
177 13
χ2 < 2.14, p > .14 …
171 18
χ2 < 2.14, p > .14 …
χ2 < 2.14, p > .14 …
χ2 (1) = 2.76, p = .10 …
184 44
χ2 (1) = 6.50, p = .01 …
χ2 (1) = 0.88, p = .35 …
p < .001
p < .001
p = .73
97 35
χ2 (1) = 8.02, p = .005 …
/
χ2 (1) = 6.24, p = .01 …
/
χ2 (1) = 0.19, p = .66 …
/
/
/
/
/
/
/
445 − 5
−5
χ2 (1) = 2.989, χ2 (1) = 0.007, χ2 (1) =
p = .084
p = .936
4.481,
p = .034
†
†
†
445 − 7
− 13
−6
χ2 (1) = 1.496, p = .221 Cramer’s V = 0.071 [− 0.058, 0.194]
χ2 (1) = 4.991, p = .025 Cramer’s V = 0.13 [− 0.058, 0.25]
χ2 (1) = 1.03, p = .31 Cramer’s V = 0.059 [− 0.058, 0.182]
```

### Table 3
*Attention check results.*

```
Response alternative “Never answer scales in online studies seriously”* “Always carefully read and answer each item on online surveys”**
Counts % of total Counts % of total
1 (Not at all characteristic of me) 834 93.7% 1 0.1%
2 (A little characteristic of me) 19 2.1% 9 1.0%
3 (Somewhat characteristic of me) 19 2.1% 19 2.1%
4 (Very characteristic of me) 14 1.6% 81 9.1%
5 (Entirely characteristic of me) 4 0.4% 780 87.6%
*M =1.13; SD =0.55 (here, lower numbers indicate higher attentiveness).
**M =4.83, SD =0.51 (here, higher numbers indicate higher attentiveness).
making definitive choices that definitive outcomes provide, compared to uncertain ones. They argued the following: when people
envision that they have passed an exam, they could easily come up with reasons to go on vacation (“let’s celebrate!”); when people
envision they have failed an exam, they could easily find opposite reasons to go on vacation (“let’s live a little!”); yet, an uncertain
outcome does not elicit good reasons to make a definitive decision.
1.1. Chosen target for replication: Tversky and Shafir (1992)
We chose Tversky and Shafir (1992) due to the impact the article has had, the lack of direct close replications, and open questions
regarding the findings (Coles, Tiokhin, Scheel, Isager, & Lakens, 2018; Lambdin & Burdsal, 2007; Li, Jiang, Dunn, & Wang, 2012). We
identified several potential contributions and clarifications that could be achieved by revisiting this classic, and we discuss those
further below.
The original article has been highly influential across disciplines because it provided a new model of decision-makers, one that is
based on rationalization and not on expected value. At the time of writing, the article had been cited 664 times according to Google
Scholar. Furthermore, highly influential theoretical papers about decision-making in psychology (Shafir, Simonson, & Tversky, 1993),
marketing (Simonson & Tversky, 1992) and management (Tversky & Simonson, 1993) were directly based on this empirical finding.
Tversky and Shafir claimed support for the disjunction effect in both “choice under risk” and “paying to know“ paradigms, and for
these to hold for both between-subject and within-subject experimental designs. Tversky and Shafir did not report any inferential
statistics in their paper, limiting the discussion of their results to descriptives.
The “choice under risk” results are not without controversy. Kühberger, Komunska, and Perner (2001) failed to replicate the
“choice under risk” problem four times, and Lambdin and Burdsal (2007) also failed to find support for a disjunction effect (as
Figure 1. Tversky and Shafir (1992) original studies’ results and present replications
```

conceptualized by the original authors). However, it may be that neither replication team had sufficient power to detect a disjunction effect in two-step gambles. Moreover, Li et al. (2012) found support for the disjunction effect in a conceptual replication involving a World Cup scenario, and mixed support for the disjunction effect in a variation of the two-steps gambles problem. Further, there are no known direct replications of the “paying to know” problem. Given the paper’s influence across fields and the controversy surrounding the findings, we decided to attempt a pre-registered well-powered replication using a between-subject design resembling the original study. We summarized our review of the current findings in the literature in Tables 1 and 2.

1.2. Extension: Testing both between-subject and within-subject designs
We decided to also test the robustness of the disjunction effect by conducting an extension, adding a conceptual replication of both the “choice under risk“ and the “paying to know” paradigms in a within-subject design (joint evaluation), in which all participants are exposed to all experimental conditions. There is some evidence that people make different judgments and decisions when evaluating different options jointly compared to when they are in separate evaluation (Hsee, 1996). Such differences are interesting for both theoretical and practical reasons, as they highlight the “on-the-fly” nature of preference construction, and may give indications on how to construct choice menus in order to achieve desired goals (Sunstein, 2018). It is not entirely clear which problems in judgments and decision-making are affected by evaluation mode, and to what extent (Lambdin & Shaffer, 2009). Note that in the original paper, results were very similar and in support of the disjunction effect when using either within-subject or the between-subject experimental designs. This extension would therefore provide theoretically interesting insights into the nature of the disjunction effect and the impact of study design on a classic problem in judgment and decision-making.

## Method

2.1. Pre-registrations and open data
We first pre-registered the experiment on the Open Science Framework (OSF) and data collection was launched later that week. Pre-registrations, disclosures, power analyses, and all materials are available in the supplementary materials. These together with datasets and code were made available on the OSF at https://osf.io/gu58m/. All measures, manipulations, and exclusions for this investigation are reported, and data collection was completed before analyses. Pre-registrations are available on the OSF: https://osf. io/fzchj.

2.2. Procedure and participants
We recruited a total of 890 participants from Mechanical Turk (405 males, 483 females, 2 other/prefer not to disclose, Mage = 40, SDage = 11.35), who were paid $1.38 for this task, administered as part of a multi-study replication effort. We ran the replications both using a between-subject design as in the original paper, and using a within-subject design, randomly assigned. Specifically, half of participants completed the “choice under risk” problem between-subject and the “paying to know” problem within-subject; the other half completed the “paying to know” problem between-subject and the “choice under risk” problem within-subject.
In the between-subject replication of choice under risk and the within-subject replication of “paying to know”, 445 participants (194 male, 250 female, 1 other/would rather not disclose, Mage = 39.2, SDage = 11.32) were randomly assigned to one of the three conditions of the “choice under risk” scenario (Win, Loss, or Uncertain) and all conditions in the “paying to know” scenario (Pass, Fail, Uncertain) presented in randomized order.
In the within-subject replication of “choice under risk” and the between-subject replication of “paying to know”, 445 participants (211 males, 233 females, 1 other/would rather not disclose, Mage = 40.1, SDage = 11.38) were randomly assigned to one of the three conditions of the “paying to know” scenario (Pass, Fail, Uncertain) and all conditions in the “choice under risk” scenario (Win, Loss, or Uncertain) presented in randomized order.
We employed two checks, which indicated that participants were very attentive (Table 3). Following our pre-registered plan, we report analyses below based on data from all participants, maximizing statistical power.

2.3. How to analyze the disjunction effect?
Lambdin and Burdsal (2007) argued that disjunction effects can only be observed using within-subject designs, i.e., by observing how participants change their choice of a bet or of a vacation in uncertain situations compared to certain situations, and then clas­ sifying them as displaying a disjunction effect. This approach certainly has merits, because of its granularity and precision. Our goal for this replication was to compare our findings with the original findings. Using Lambdin and Burdsal (2007) approach is unfeasible, as it would require the original data and to limit the comparison to only a within-subject design. Further, using Lambdin and Burdsal (2007)’s method is uninformative for our goals, as Tversky and Shafir (1992) measured the disjunction effect at the group level in between-subjects studies, and at the condition level in within-subjects. For both these reasons (unfeasibility and impossibility of comparison), we decided to compare group proportions as in the original paper.

2.4. Scenarios

2.4.1. “Paying to know” In the “paying to know“ paradigm, participants read the following scenarios (differences between the scenarios are underlined):
[Pass/Fail Version] “Imagine that you have just taken a tough qualifying examination. It is the end of the semester, you feel tired and run-down, and you find out that you [passed the exam / failed the exam. You will have to take it again in a couple of months—after the Christmas holidays.] You now have an opportunity to buy a very attractive 5-day Christmas vacation package to Hawaii at an exceptionally low price. The special offer expires tomorrow. [Uncertain Version] “Imagine that you have just taken a tough qualifying examination. It is the end of the fall quarter, you feel tired and run-down, and you are not sure that you passed the exam. In case you failed you have to take the exam again in a couple of months—after the Christmas holidays. You now have an opportunity to buy a very attractive 5-day Christmas vacation package to Hawaii at an exceptionally low price. The special offer expires tomorrow, while the exam grade will not be available until the following day. Once presented with a scenario, participants had to make a choice between three options: 1) “I would buy the vacation package“, 2) “I would not buy the vacation package”, and 3) “I would pay a $5 nonrefundable fee in order to retain the rights to buy the vacation package at the same exceptional price the day after tomorrow“.

2.4.2. “Choice under risk” In the “choice under risk“ scenario, participants were assigned to one of the following scenarios:
[Win/Loss version] “Imagine that you have just played a game of chance that gave you a 50% chance to win $200 and a 50% chance to lose $100. The coin was tossed and you have [won $200 / lost $100]. You are now offered a second identical gamble: 50% chance to win $200 and 50% chance to lose $100 [Uncertain version] “Imagine that the coin has already been tossed, but that you will not know whether you have won $200 or lost $100 until you make your decision concerning a second, identical gamble: 50% chance to win $200 and 50% chance to lose $100 Once presented with a scenario, participants then indicated whether they would accept or reject the second bet.

2.5. Clarifications about effect sizes

Across between-subject scenarios, we used Cramer’s V as a standardized effect size. However, Cramer’s V is bounded at 0 and 1. One could therefore find similar Cramer’s V in two studies, but a completely different pattern of results. Further, the calculation of 95% CIs around Cramer’s V is problematic for the same reason. We calculated 95% CIs with the R package DescTools (Signorell, 2016) that provides with negative pseudo-lower bounds. Finally, Cramer’s V cannot be used for within-subject designs. We chose to include it to give a broader indication of an unstandardized effect size, but given these limitations, we caution against the over-reliance on Cramer’s V and instead invite the reader to give more weight to descriptive statistics.

## Results

Descriptives and inferential statistics are provided in Tables 1 and 2, and findings are plotted in Fig. 1.

3.1. “Paying to know”

3.1.1. Between-subject design replication In the Fail condition, only 22/144 (15%) participants chose to pay the $5 to reserve the vacation price, in the Pass condition, this
proportion increased to 52/148 (35%), and in the Uncertain condition 99/153 (65%) participants indicated that they would pay the $5. This pattern was largely consistent with the original results, with a sharp increase in the proportion of participants choosing to pay $5 to reserve in the Uncertain condition compared to the Pass and the Fail conditions.
We conducted a test for equality of proportions and found support for an omnibus effect of condition on decision (χ2 (4) = 81.00, p < .001, Cramer’s V = 0.302, [0.239, 0.368]). We proceeded to conduct three pairwise tests for equality of proportion. We found support for differences between the Pass and the Fail conditions (χ2 (2) = 17.53, p < .001, Cramer’s V = 0.245, [0.146, 0.363]), support for differences between the Fail and the Uncertain conditions (χ2 (2) = 75.24, p < .001, Cramer’s V = 0.503, [0.394, 0.619]), and

support for differences between the Pass and the Uncertain conditions (χ2 (2) = 28.88, p < .001, Cramer’s V = 0.31, [0.207, 0.426]). Dwass-Steel-Critchlow-Fligner comparisons in a Kruskal-Wallis ANOVA, which control for multiple comparisons, showed no support for differences between the Pass and the Fail conditions (W = 3.153, p = .066), and support for differences between the Fail and the Uncertain conditions (W = 11.34, p < .001) and for the Pass and the Uncertain conditions (W = 7.58, p < .001).

3.1.2. Within-subject design replication In the Fail condition, 71/445 (16%) participants chose to pay the $5 to reserve the vacation price, in the Pass condition this
proportion increased to 92/445 (21%), and in the Uncertain condition 178/445 (40%) participants indicated that they would pay the $5. As in the between-subject replication, this pattern of results was consistent with original findings.
We conducted three pairwise multiple comparisons using McNemar’s test for repeated measures. We found support for differences between the Pass and Fail conditions (χ2 (3) = 138.38, p < .001), support for differences between the Fail and the Uncertain condition (χ2 (3) = 85.72, p < .001), and support for difference between the Pass and the Uncertain conditions (χ2 (3) = 152.08, p < .001). In a Friedman test and series of Durbin-Conover comparisons, which correct for multiple comparisons, we found support for an omnibus effect of condition (χ2 (2) = 132.678, p < .001; Uncertain – Pass statistic = 12.436, p < .001; Uncertain – Fail statistic = 7.05, p < .001; Pass – Fail statistic = 5.386, p < .001).

3.1.3. “Paying to know” summary: Comparing between and within designs Overall, in both the within-subject and the between-subject replications we found effects consistent with the original findings. We
found an increase in the share of participants reporting that they would pay $5 to reserve the price of the vacation in the Uncertain condition, compared to the two other conditions. The share of participants who decided not to buy the vacation was higher across our replications in all conditions.

3.2. “Choice under risk”

3.2.1. Between-subject replication In the “Win” condition, 46/148 (31%) participants chose to accept the gamble, in the “Loss” condition, 56/148 participants (38%)
chose to accept the gamble, and in the “Uncertain” condition 65/149 (44%) participants chose to accept the gamble. This pattern was inconsistent with the original findings, and in direct contrast to original results. We expected the proportion of participants who chose to accept the bet to decrease in the Uncertain condition compared to the other two conditions, and yet we found that only a minority of participants accepted the bet across all conditions. We conducted a test of equality of proportion with condition (win, loss, uncertain) as the independent variable and choice (accept; reject) as the dependent variable and indeed failed to find support for the effect (χ2 (2) = 4.99, p = .082, Cramer’s V = 0.106, 95% CI [− 0.067, 0.202].)
We followed by conducting three pairwise tests for equality of proportions. We found support for differences between the Win and the Uncertain conditions (χ2 (1) = 4.991, p = .025, Cramer’s V = 0.13 [− 0.058, 0.25]), albeit in a direction opposite to the original findings. We found no support for differences between the Win and the Loss conditions (χ2 (1) = 1.496, p = .221, Cramer’s V = 0.071 [− 0.058, 0.194]) or for differences between the Loss and the Uncertain conditions (χ2 (1) = 1.03, p = .31, Cramer’s V = 0.059 [− 0.058, 0.182]). Dwass-Steel-Critchlow-Fligner comparisons in a Kruskal-Wallis ANOVA, which correct for multiple comparisons (Douglas & Michael, 2007), and again found no evidence for any differences between conditions (Loss-Win: W = 1.73, p = .441; Loss-Uncertain: W = -1.43, p = .569; Win - Uncertain: W = -3.15, p = .066).

3.2.2. Within-subject replication In the Win condition 164/445 (37%) participants chose to accept the gamble, in the Loss condition 187/445 (42%) participants
chose to accept the gamble, and in the Uncertain condition 165/445 (37%) chose to accept the gamble. Comparing the certain con­ ditions (Win, Loss) with the Uncertain condition, we failed to find support for a disjunction effect. Again, as in the between-subject design findings, this pattern was not consistent with the original findings. Whereas original findings pointed to the majority of par­ ticipants accepting the bet in both the Win and the Loss conditions, and a minority accepting the bet in the Uncertain condition, we found that the minority accepted the bet across all conditions.
We ran a Cochran test for equality of outcomes in a repeated-measures design and found no support for an effect (Cochran’s Q (2) = 4.63, p = .099). We conducted three pairwise McNemar test for repeated-measures equality of proportions, and found no support for differences between the Win and the Loss conditions (χ2 (1) = 2.989, p = .084), some support for differences between the Loss and the Uncertain condition (χ2 (1) = 4.481, p = .034), and no support for differences between the Win and the Uncertain condition (χ2 (1) = 0.007, p = .936). Similar results were obtained using the Durbin-Conover pairwise comparisons, which correct for multiple com­ parisons (Conover & Iman, 1979) (Uncertain – Win statistic = 0.083, p = .934; Uncertain – Loss statistic = 1.823, p = .069; Win – Loss statistic = 1.906, p = .057).

3.2.3. “Choice under risk” summary: Comparing between and within designs In both replications using different designs only a minority of participants accepted the second bet, whereas in the original studies a
majority of participants chose to accept the bet in the Win and the Loss conditions, but only a minority chose to accept it in the Uncertain condition.

4. General discussion

We conducted a replication of disjunction effect (Tversky & Shafir, 1992), testing two paradigms. Our results were consistent with original findings for the “paying to know” paradigm, but inconsistent with a much weaker effect than original findings in the “choice under risk” paradigm. We ran each of the two paradigms using two designs, between-subject and within-subject, and results were very consistent across designs.

4.1. Replications results

Two and a half decades after the publication of the original findings, we were able to successfully replicate the findings regarding “paying to know“ scenario, regardless of research design, showing support for the robustness and reliability of the disjunction effect. With that said, we identified a caveat in a failed replication for the “choice under risk” scenario. Moving forward, those who aim to study the disjunction effect further may want to base their follow-ups on what was successfully replicated, or to investigate factors that led to the differences between the two paradigms.
What may explain differences between the original article and the present replications? An immediate suspect is the participants we recruited, and their demographic features. The original experiment employed Stanford undergraduates, and we employed online MTurk samples, which have been shown reliable (Buhrmester, Kwang, & Gosling, 2011; Coppock, 2017; Coppock, Leeper, & Mullinix, 2018; Zwaan et al., 2018), especially so in the domain of judgement and decision making replications, with replications from the economic psychology and judgment and decision-making yielding highly similar results even more than 20 years later (Chandrashekar et al., 2021; Ziano, Jie, et al., 2020; Ziano, Wang, et al., 2020; Ziano, Mok, & Feldman, 2020). Yet, we consider it unlikely that the sample is to blame for the failed replication of the “choice under risk” problem, when at the same time demonstrating a successful replication of the “paying to know” problem.
Second, some may argue that the passing of time may have affected replication results. The original studies were conducted on or before 1992. It is possible that the meaning of the “choice under risk” problem factors has changed during that time. Again, this account does not explain why the “paying to know” problem was successfully replicated. It is possible that the passing of time has affected the two problems differently, yet given the broad context-less descriptions of the gambles in that scenario, we find this argument unconvincing.
Third, it is possible that the “choice under risk“ problem was a false-positive finding (given the smaller effect size we found compared to the original paper), whereas the “paying to know” problem was a true positive finding. We provide two arguments in support of this explanation. First, previous research failed to find a disjunction effect in two-steps gambles, using either a betweensubject design or a within-subject design (Kühberger et al., 2001; Lambdin & Burdsal, 2007), or found mixed results in conceptual replications (Li et al., 2012). Second, Tversky and Shafir (1992) report two successful replications of the “choice under risk” problem (p. 307), yet also report that increasing the stakes in the initial gamble (but leaving the second gamble unchanged) led to no disjunction effect, presumably because additional gambles did not provide strong enough reasons since the stakes were lower in comparison to first one. Possibly, this account of Tversky and Shafir (1992)’s failed two-step gambles rerun with modified amounts may be an indication of their own first failed replication of the disjunction effect.
An additional possibility, suggested by a recent paper (Broekaert, Busemeyer, & Pothos, 2020), is that risk-aversion may moderate the extent to which people exhibit the disjunction effect, such that less risk-averse people do not exhibit the effect, and that a quantumdynamic model can reconcile opposing results from the original paper and from unsuccessful replication. This investigation falls outside the purview of this paper, but it seems a potentially fruitful avenue for future research.
Overall, these results pose a challenge for research based on the disjunction effect. With inconsistent evidence for the two problems, which of the problems is to be associated with the disjunction effect? Though we now have fairly clear criteria for summarizing a replication for a single hypothesis with a single association between two variables, we still lack the criteria to evaluate complex replications with mixed findings, and then relate that back underlying theory. Further research is needed to disentangle when and why supposedly irrelevant uncertain outcomes cause preference reversals. There is also much need for to establishing clearer criteria in evaluating complex replication efforts, of multiple studies, multiple hypotheses, and multiple independent and dependent variables, all representing a single theory or article.

4.2. Comparing research designs

We found consistent results across within-subject and between-subject designs. We did not find larger differences in the withinsubjects condition compared to the between-subjects condition in the Paying to Know scenario. While there was pattern of choices more pronounced and more similar to the original results in the Win and Loss condition for the within-subjects condition, there was a more pronounced pattern for the Uncertain condition in the between-subjects condition. Comparisons of evaluation modes is highly relevant for both theoretical and practical purposes, as it highlights the fickle nature of preferences and choices that people make in different situations (Sunstein, 2018). This is an important contribution, as there are conflicting findings in judgment and decisionmaking, some showing differences between joint evaluations (within-subject) and separate evaluations (between-subject) (e.g., Hsee, 1996; Hsee, Loewenstein, Blount, & Bazerman, 1999; Paharia, Kassam, Greene, & Bazerman, 2009) whereas others show effects robust to evaluation mode change (Lambdin & Shaffer, 2009; Ziano, Lembregts, & Pandelaere, 2019; Ziano & Pandelaere, 2020).
We identified a methods gap regarding comparisons of within- and between- subject experiments. Although there are methods for such comparisons for frequentist linear dependent variables (e.g., Sezer, Zhang, Gino, & Bazerman, 2016), methods are still lacking

regarding similar analyses for binomial or multinomial dependent variables. This poses a challenge for comparisons of joint and separate evaluations from an inferential point of view (beyond descriptives in Tversky & Shafir, 1992), and it is a promising issue to tackle in future research.

Author bios

Ignazio Ziano is an assistant professor with the Grenoble Ecole de Management marketing department, F-38000 Grenoble (France). His research focuses on judgment and decision-making and consumer behavior.
Gilad Feldman is an assistant professor with the University of Hong Kong psychology department. His research focuses on judgment and decision-making.
Man Fai Kong, Hong Joo Kim, Chit Yu Liu, Sze Chai Wong were students at the University of Hong Kong during academic year 2018. Bo Ley Cheng was a teaching assistant at the University of Hong Kong psychology department during academic year 2018.

Authorship declaration

Gilad led the reported replication effort in advanced social psychology and judgment and decision-making courses (PSYC2071/ 3052). Gilad supervised each step in the project, conducted the pre-registration, and ran data collection. Ignazio reanalyzed and validated all findings, added additional analyses and reports, and integrated all reports into a manuscript. Ignazio and Gilad jointly finalized the manuscript for submission.
Man Fai Kong, Hong Joo Kim, Chit Yu Liu, Sze Chai Wong designed the replication, wrote the pre-registrations, analyzed the findings and wrote an initial report of the findings as part of their course. Man Fai Kong designed and initiated the between-within design contrast extension.
Bo Ley Cheng guided and assisted the replication effort.

## Financial disclosure/funding

This research was supported by the European Association for Social Psychology seedcorn grant.

## Declaration of Competing Interest

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

## References

Broekaert, J. B., Busemeyer, J. R., & Pothos, E. M. (2020). The Disjunction Effect in two-stage simulated gambles. An experimental study and comparison of a heuristic logistic, Markov and quantum-like model. Cognitive Psychology, 117(November 2019), 101262. https://doi.org/10.1016/j.cogpsych.2019.101262
Buhrmester, M., Kwang, T., & Gosling, S. D. (2011). Amazon’s mechanical Turk: A new source of inexpensive, yet high-quality, data? Perspectives on Psychological Science, 6(1), 3–5. https://doi.org/10.1177/1745691610393980
Chandrashekar, P., Yeung, W., Yau, K. C., Feldman, G., Yuen Ting Julie, M., Ho, J. C., & Chan, C. (2021). Agency and self-other asymmetries in perceived bias and shortcomings: Replications of the Bias Blind Spot and extensions linking to free will beliefs. Preprint, (March)https://doi.org/10.13140/RG.2.2.19878.16961
Coles, N., Tiokhin, L., Scheel, A. M., Isager, P. M., & Lakens, D. (2018). The costs and benefits of replication studies. https://psyarxiv.com/c8akj/. Conover, W. J., & Iman, R. L. (1979). On multiple-comparisons procedures. Los Alamos Sci. Lab Tech. Rep. LA-7677-MS, 1–14. Coppock, A. (2017). Generalizing from survey experiments conducted on mechanical Turk: A replication approach. Political Science Research and Methods. https://doi.
org/http://alexandercoppock.com/papers/Coppock_generalizability.pdf. Coppock, A., Leeper, T. J., & Mullinix, K. J. (2018). Generalizability of heterogeneous treatment effect estimates across samples. In Proceedings of the National Academy
of Sciences (p. 201808083). https://doi.org/10.1073/pnas.1808083115 Douglas, C. E., & Michael, F. A. (2007). On distribution-free multiple comparisons in the one-way analysis of variance. Communications in Statistics - Theory and

## Methods

20(1), 127–139. https://doi.org/10.1080/03610929108830487 Hsee, C. K. (1996). The evaluability hypothesis: An explanation for preference reversals between joint and separate evaluations of alternatives. Organizational Behavior
and Human Decision Processes, 67(3), 247–257. https://doi.org/10.1006/obhd.1996.0077 Hsee, C. K., Loewenstein, G. F., Blount, S., & Bazerman, M. H. (1999). Preference reversals between joint and separate evaluations of options: A review and theoretical
analysis. Psychological Bulletin, 125(5), 576–590. https://doi.org/10.1037/0033-2909.125.5.576 Kühberger, A., Komunska, D., & Perner, J. (2001). The disjunction effect: Does it exist for two-step gambles? Organizational Behavior and Human Decision Processes, 85
(2), 250–264. https://doi.org/10.1006/obhd.2000.2942 Lambdin, C., & Burdsal, C. (2007). The disjunction effect reexamined: Relevant methodological issues and the fallacy of unspecified percentage comparisons.
Organizational Behavior and Human Decision Processes, 103(2), 268–276. https://doi.org/10.1016/j.obhdp.2006.04.001 Lambdin, C., & Shaffer, V. A. (2009). Are within-subjects designs transparent? Judgment and Decision Making, 4(7), 554–566. https://doi.org/10.1037/e722352011-
194 Li, S., Jiang, C., Dunn, J. C., & Wang, Z. (2012). A test of “reason-based“ and “reluctance-to-think” accounts of the disjunction effect . A test of ‘“reason-based”’ and
‘“reluctance-to-think”’ accounts of the disjunction effect, (January). https://doi.org/10.1016/j.ins.2011.09.002. Paharia, N., Kassam, K. S., Greene, J. D., & Bazerman, M. H. (2009). Dirty work, clean hands: The moral psychology of indirect agency. Organizational Behavior and
Human Decision Processes, 109(2), 134–141. https://doi.org/10.1016/j.obhdp.2009.03.002 Savage, L. J. (1954). The foundations of statistics. New York, New York, USA: Wiley. Sezer, O., Zhang, T., Gino, F., & Bazerman, M. H. (2016). Overcoming the outcome bias: Making intentions matter. Organizational Behavior and Human Decision
Processes, 137, 13–26. https://doi.org/10.1016/j.obhdp.2016.07.001 Shafir, E., Simonson, I., & Tversky, A. (1993). Reason-based choice. Cognition, 49(1), 11–36. https://doi.org/10.1016/0010-0277(93)90034-S Signorell, A. (2016). DescTools: Tools for descriptive statistics. R Package Version 0.99, 18.

Simonson, I., & Tversky, A. (1992). Choice in context : Tradoff CONTRAST AND EXTREMENESS AVErsion. Journal of Marketing Research, 29(3), 281–295. https://doi. org/10.2307/3172740
Sunstein, C. R. (2018). On preferring A to B, while also preferring B to A. Rationality and Society, 30(3), 305–331. Tversky, A., & Shafir, E. (1992). The disjunction effect in choice under uncertainty. Retrieved from Psychological Science, 3(5), 305–309 https://0-journals-sagepub-
com.wam.city.ac.uk/doi/pdf/10.1111/j.1467-9280.1992.tb00678.x. Tversky, A., & Simonson, I. (1993). Context- dependent preferences. Management Science, 39(10), 1179–1189. https://doi.org/10.1287/mnsc.39.10.1179 Ziano, I., Lembregts, C., & Pandelaere, M. (2019). Perceived Income Inequality: Why Pay Ratios Are Less Effective Than Median Incomes. Retrieved from https://
psyarxiv.com/2zngf/. Ziano, I., & Pandelaere, M. (2020). Late-Action Bias: Perceived Outcome Reversibility and Heightened Counterfactual Thinking Make Actions Closer to a Definitive
Outcome Seem More Impactful. https://doi.org/10.1017/CBO9781107415324.004. Ziano, I., Wang, Y. J., Sany, S. S., Feldman, G., Ngai, L. H., Lau, Y. K., … Chan, C. (2020). Perceived morality of direct versus indirect harm : Replications of the
preference for indirect harm effect In press at Meta Psychology . Accepted for publication on Jan 30, 2020. Meta-Psychology. Retrieved from https://psyarxiv.com/ bs7jf. Ziano, I., Mok, P. Y., & Feldman, G. (2020). Replication and Extension of Alicke (1985) Better-Than-Average Effect for Desirable and Controllable Traits. Social Psychological and Personality Science, 1948550620948973. Ziano, I., Jie, L., Man, T. S., Ching, L. H., Anil, K. A., Cheng, B. L., & Feldman, G. (2020). Revisiting “Money Illusion”: Replication and Extension of Shafir, Diamond, and Tversky (1997). Journal of Economic Psychology, 102349. Zwaan, R. A., Pecher, D., Paolacci, G., Bouwmeester, S., Verkoeijen, P., Dijkstra, K., & Zeelenberg, R. (2018). Participant Nonnaivet´e and the reproducibility of cognitive psychology. Psychonomic Bulletin and Review, 25(5), 1968–1972. https://doi.org/10.3758/s13423-017-1348-y


## Figures

*Figure 1. Fig. 1. Tversky and Shafir (1992) original studies’ results and present replications results. 5*


## Tables (unlocated in body)

### Table 2
*Comparison of differences across conditions.*

```
Paying to know, , difference in % Pay $5 across conditions Choice under risk, difference in % Accept across conditions
N Pass-Fail Pass-Uncertain Fail-Uncertain N Win-Loss Win-: Loss-
Uncertain Uncertain
Tversky & Shafir, 1992 / / / / 98 10 35 25
(within-subjects)
Inferential statistics / / / / … … …
Effect size [95% CI] / / / / † † †
Tversky & Shafir, 1992 199 (cid:0) 1 (cid:0) 31 (cid:0) 30 213 14 31 17
(between-subjects)
Inferential statistics χ2 (2) =0.552, χ2 (2) =14.437, χ2 (2) = χ2 (1) =1.927, χ2 (1) = χ2 (1) =4.07,
p =.759 p <.001 12.676, p = p =.165 12.484, p < p =.04
.001 .001
Effect size [95% CI] Cramer’s V = Cramer’s V = Cramer’s V = Cramer’s V = Cramer’s V = Cramer’s V =
0.064 0.329 0.308 0.131 0.31 0.183
[(cid:0) 0.122, [0.188, 0.505] [0.171, 0.484] [(cid:0) 0.083, [0.168, 0.482] [0.08, 0.357]
0.231] 0.307]
Tversky & Shafir, 1992, / / / / 171 (cid:0) 2 1 (cid:0) 4
modified gambles
(between-subjects)
Inferential statistics / / / / χ2 (1) =0.171, χ2 (1) <0.001, χ2 (1) =
p =.68 p >.99 0.391,
p =.531
Effect size [95% CI] / / / / Cramer’s V = Cramer’s V = Cramer’s V =
0.058 0.02 0.078
[(cid:0) 0.094, [(cid:0) 0.093, [(cid:0) 0.094,
0.258] 0.207] 0.278]
Kühberger et al., 2001, exp. 1 / / / / 177 13 13 0
(between-subject)
Inferential statistics / / / / χ2 <2.14, χ2 <2.14, χ2 <2.14,
p >.14 p >.14 p >.14
Effect size [95% CI] / / / / … … …
Kühberger et al., 2001, exp. 2 / / / / 171 18 26 6
(between-subject)
Inferential statistics / / / / χ2 (1) =2.76, χ2 (1) =6.50, χ2 (1) =0.88,
p =.10 p =.01 p =.35
Effect size [95% CI] / / / / … … …
Kühberger et al., 2001, exp. 3 / / / / 184 44 39 5
(within-subject)
Inferential statistics / / / / p <.001 p <.001 p =.73
Effect size [95% CI] / / / /
Kühberger et al., 2001, exp. 4 / / / / 97 35 30 5
(between-subject)
Inferential statistics / / / / χ2 (1) =8.02, χ2 (1) =6.24, χ2 (1) =0.19,
p =.005 p =.01 p =.66
Effect size [95% CI] / / / / … … …
Lambdin & Burdsal, 2007 35 17 26 9 / / /
(within-subject)
Inferential statistics … … … / / /
Effect size [95% CI] … … … / / /
Present work 445 (cid:0) 5 (cid:0) 19 (cid:0) 24 445 (cid:0) 5 0 (cid:0) 5
(within-subject)
Inferential statistics χ2 (3) = χ2 (3) =152.08, χ2 (3) =85.72, χ2 (1) =2.989, χ2 (1) =0.007, χ2 (1) =
138.38, p <.001 p <.001 p =.084 p =.936 4.481,
p <.001 p =.034
Effect size [95% CI] † † † † † †
Present work 445 (cid:0) 20 (cid:0) 30 (cid:0) 50 445 (cid:0) 7 (cid:0) 13 (cid:0) 6
(between-subject)
Inferential statistics χ2 (2) =17.53, χ2 (2) =28.88, χ2 (2) =75.24, χ2 (1) =1.496, χ2 (1) =4.991, χ2 (1) =1.03,
p <.001 p <.001 p <.001 p =.221 p =.025 p =.31
Effect size [95% CI] Cramer’s V = Cramer’s V = Cramer’s V = Cramer’s V = Cramer’s V = Cramer’s V =
0.245 0.31 [0.207, 0.503 0.071 0.13 0.059
[0.146, 0.363] 0.426] [0.394, 0.619] [(cid:0) 0.058, [(cid:0) 0.058, 0.25] [(cid:0) 0.058,
0.194] 0.182]
†
No appropriate omnibus effect size.
/Absent.
- - - Impossible to recalculate from original
```
