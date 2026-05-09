C:\Users\filin\AppData\Roaming\Python\Python314\site-packages\camelot\parsers\base.py:238: UserWarning: No tables found in table area (62.010457608320294, 132.0927936741439, 535.6944618512331, 727.610002087536)
  cols, rows, v_s, h_s = self._generate_columns_and_rows(bbox, user_cols)
C:\Users\filin\AppData\Roaming\Python\Python314\site-packages\camelot\parsers\base.py:238: UserWarning: No tables found in table area (85.78447662752001, 665.4845403872002, 190.33598470867238, 804.392865736)
  cols, rows, v_s, h_s = self._generate_columns_and_rows(bbox, user_cols)
C:\Users\filin\AppData\Roaming\Python\Python314\site-packages\camelot\parsers\base.py:238: UserWarning: No tables found in table area (98.01908641520001, 576.5644692512, 548.1160891325269, 730.7985846384)
  cols, rows, v_s, h_s = self._generate_columns_and_rows(bbox, user_cols)
C:\Users\filin\AppData\Roaming\Python\Python314\site-packages\camelot\parsers\base.py:238: UserWarning: No tables found in table area (98.02008641599998, 370.3743042992, 552.3688980947712, 538.9717645104)
  cols, rows, v_s, h_s = self._generate_columns_and_rows(bbox, user_cols)
C:\Users\filin\AppData\Roaming\Python\Python314\site-packages\camelot\utils.py:1217: UserWarning:   (559.560447648, 562.055489644032) does not lie in column range (293.90999999999997, 558.9599999999999)
  warnings.warn(
C:\Users\filin\AppData\Roaming\Python\Python314\site-packages\camelot\utils.py:1217: UserWarning:   (576.120460896, 578.615502892032) does not lie in column range (107.52, 575.88)
  warnings.warn(
C:\Users\filin\AppData\Roaming\Python\Python314\site-packages\camelot\utils.py:1217: UserWarning:   (604.680483744, 607.6804861439999) does not lie in column range (146.4, 604.1999999999999)
  warnings.warn(
C:\Users\filin\AppData\Roaming\Python\Python314\site-packages\camelot\utils.py:1217: UserWarning:   (604.680483744, 607.6804861439999) does not lie in column range (108.0, 604.68)
  warnings.warn(
Meta-Psychology, 2023, vol 7, MP.2022.3108 https://doi.org/10.15626/MP.2022.3108 Article type: Replication Report Published under the CC-BY4.0 license

Open data: Yes Open materials: Yes Open and reproducible analysis: Yes Open reviews and editorial process: Yes Preregistration: Yes

Edited by: Rickard Carlsson Reviewed by: Streamlined Peer Review Analysis reproduced by: Haojiang Ying All supplementary ﬁles can be accessed at OSF: https://doi.org/10.17605/OSF.IO/RDZJT

## Abstract

Defaults versus framing: Revisiting Default Effect and Framing Effect with a replication and extension of Johnson and Goldstein
(2003) and Johnson, Bellman, and Lohse (2002)
Subramanya Prasad Chandrashekar*1, Nadia Adelina*2, Shiyuan Zeng*2, Yan Ying Esther Chiu*2, Grace Yat Sum Leung*2, Paul Henne3, Boley Cheng2, and Gilad Feldman2
1Department of Psychology, Norwegian University of Science and Technology (NTNU) 2Department of Psychology, University of Hong Kong, Hong Kong SAR 3Department of Philosophy, Lake Forest College
*Joint ﬁrst authors People tend to stick with a default option instead of switching to another option. For instance, Johnson and Goldstein (2003) found a default effect in an organ donation scenario: if organ donation is the default option, people are more inclined to consent to it. Johnson et al. (2002) found a similar default effect in health-survey scenarios: if receiving more information about your health is the default, people are more inclined to consent to it. Much of the highly cited, impactful work on these default effects, however, has not been replicated in well-powered samples. In two well-powered samples (N = 1920), we conducted a close replication of the default effect in Johnson and Goldstein (2003) and in Johnson et al. (2002). We successfully replicated Johnson and Goldstein (2003). In an extension of the original ﬁndings, we also show that default effects are unaffected by the permanence of these selections. We, however, failed to replicate the ﬁndings of Johnson et al. (2002)’s study; we did not ﬁnd evidence for a default effect. We did, however, ﬁnd a framing effect: participants who read a positively-framed scenario consented to receive health-related information at a higher rate than participants who read a negatively framed scenario. We also conducted a conceptual replication of Johnson et al. (2002) that was based on an organ-donation scenario, but this attempt failed to ﬁnd a default effect. Our results suggest that default effects depend on framing and context. Materials, data, and code are available on: https://osf.io/8wd2b/.

## Keywords

action framing effect; default effect; organ donation; nudge; replication; choice; judgment and decision making

Suppose that people receive a health survey after a doctor’s appointment in order to see if they would like to receive health updates from their doctors. If the option to participate is preselected, people would probably not change their response—instead sticking with the default option and participating in the service. This is an example of the default effect: given a default option, people stick with it rather than changing (Johnson and Goldstein, 2003; Johnson et al., 1993).
The framing of the options may also affect people’s choices. In this example, people would be more inclined to select an option if it is framed positively, as in answering “Yes" to "I will participate,” as opposed to negatively, as in selecting “No" to "I will not participate.” This is an example of a framing effect: people consent to participate at a higher rate when a choice is positively framed than when it is negatively framed (Johnson and

## Introduction

Goldstein, 2003). Default effects and framing effects have been very in-
ﬂuential across many academic disciplines and in public policy (Araña and León, 2013; Evans et al., 2011; Johnson and Goldstein, 2003; Mintz and Redd, 2003; Tversky and Kahneman, 1981). The use of default effects is a well-known effective example of leveraging behavioral insights to inﬂuence people or to nudge them toward speciﬁc socially desirable choices. Governments and public policy organizations worldwide have set-up Nudge Units that implemented interventions using default effects to encourage desired behavior encouraging organ donations and pension savings (Halpern, 2015).
There is, however, some evidence for an overestimation of the size of nudge effects. For instance, DellaVigna and Linos (2022) recently found that there were larger effect sizes for nudge interventions reported in

published literature than those reported by Nudge Units in the United States. This ﬁnding suggests that selective reporting may lead to inﬂated meta-analytic effect sizes (Kvarven et al., 2020). Moreover, in some cases, nudge effects did not replicate with larger samples (Bohner and Schlüter, 2014;Kettle et al., 2017; Kristal et al., 2020).
Given these recent ﬁndings, there is reason to investigate default effects and framing effects. Despite a substantial number of experimental studies on default effects, for instance, very few of these employed preregistered analysis plans using well-powered samples (Szaszi et al., 2018). Together, these may lead to misplaced optimism about easy-to-implement nudging interventions, while much more complex solutions involving structural reforms have been ignored (Schmidt and Engelen, 2020). As such, researchers have called for more preregistered replications using well-powered samples (Ferguson and Heene, 2012; Franco et al., 2014).
In the current research, we sought to revisit and reassess classics on default and framing effects by embarking on preregistered high-power replications and extensions of two impactful studies on default effects: Johnson and Goldstein (2003) and Johnson et al. (2002). The ﬁrst study by Johnson and Goldstein (2003) was an early demonstration of default effects. The study found that people were more likely to register as organ donors when the default option was to register. Johnson et al. (2002) contrasted default effects against framing effects and found that default effects prevailed, and that framing did not change the participants’ tendency to select the default over alternatives. We investigated these foundational studies.
Default Effect
Early demonstrations of default effect were in the context of auto-insurance choices made in New Jersey and Pennsylvania, when each state had a different policy regarding the right to sue for damages in auto accidents (Johnson et al., 1993). New Jersey residents had low insurance premiums yet could acquire an additional right to sue at an additional cost. Pennsylvanian residents by default had the right to sue, but they could opt out of this right and pay a lower insurance premium. For instance, Johnson et al. (1993) found that 75% of Pennsylvania auto-insurance consumers paid the higher premium and retained their right to sue. In comparison, only 20% of New Jersey auto-insurance consumers actively chose to pay the additional premium and obtain the right to sue. Researchers have since found support for the default effect in a variety of contexts related to health, retirement saving, organ donation, sustainability, insurance coverage, electricity consump-

tion, charitable giving, and many other decision-making domains (Abadie and Gay, 2006; Benartzi and Thaler, 1999;Cronqvist and Thaler, 2004; Ebeling, 2013; Jachimowicz et al., 2019; Madrian and Shea, 2001; Shealy and Klotz, 2015)1. While a few studies failed to support default effects (Abhyankar et al., 2014; Everett et al., 2015; Keller et al., 2011; Reiter et al., 2012), a recent meta-analysis noted substantial variations in the efﬁcacy of the default effects (Jachimowicz et al., 2019); for instance, defaults in consumer domains were more effective, while defaults in environmental domains were less effective (Jachimowicz et al., 2019).
Framing Effects
People’s decisions are also inﬂuenced by the way a decision scenario is framed—whether by using different wordings, settings, or situations (Brewer and Kramer, 1986; De Martino et al., 2006; Fagley and Miller, 1987; Gamliel and Kreiner, 2013; Huber et al., 1987; Kramer, 1989; Kühberger, 1998; Levin and Gaeth, 1988; Piñon and Gambara, 2005; Puto, 1987; Rothman and Salovey, 1997). Johnson et al. (2002) tested the action framing effects of a decision by manipulating whether participants were asked to select (positive frame) or reject (negative frame) an option. Participation rates in the positively framed condition were higher than the negatively framed condition. In this case, the positive or negative framing greatly inﬂuenced people decisions. The ﬁndings are consistent with the view that positive dimensions of a choice are weighted more when selecting an option whereas the negative dimensions are weighted more when rejecting an option (Shaﬁr et al., 1993).
Present research
We selected Johnson and Goldstein (2003) and Johnson et al. (2002) as our replication targets for three reasons: each is foundational, has been highly inﬂuential in academia (Kahneman, 2003; Kruglanski and Gigerenzer, 2011; Weber and Johnson, 2009), and has been highly inﬂuential in practice for policy making.
Johnson and Goldstein (2003)’s work was the ﬁrst to demonstrate the use of defaults in an organ donation scenario, and at the time of writing this article the paper has been cited more than 2000 times. In the original study, the experimenters varied whether the donor or non-donor status was the default option. Organ donation rates were higher when the default option was
1Although not directly relevant to the current study, researchers have offered a variety of explanations for default effects (e.g., Brown and Krishna, 2004; Huh et al., 2014; Johnson and Goldstein, 2003; McKenzie et al., 2006)

to donate (82%) than when the default option was to not donate (42%). These ﬁndings have inﬂuenced public policy decisions; Argentina (Nacion, 2005), Uruguay (Trujillo, 2013), Chile (Zúñiga-Fajuri, 2015), England (English et al., 2019), and Wales (Grifﬁths, 2013; Madden et al., 2020) have adopted default organ-donor status policies. Organ donation statistics from the Organization for Economic Cooperation and Development (OECD) countries show that, on average, organ donation rates are higher in countries where the default option is to donate (Opt-Out system) than in countries where the default option was not to donate (Opt-In system) (Li and Nikolka, 2016).
To the best of our knowledge, Johnson et al. (2002) were the ﬁrst to investigate the interaction of framing of action (we refer to this framing effect here as an action framing effect)2 and default effects in people’s decisions. In the original study, the researchers asked participants whether they would like to be notiﬁed about future health surveys after they completed an online health questionnaire (Johnson et al., 2002). The experimenters varied whether the default selection was to receive these future notiﬁcations, not to receive these future notiﬁcations, or neither. They also varied whether the options were framed positively (“Notify Me”) or negatively (“Do Not Notify Me”). Consistent with the default effect, participants were more inclined to be notiﬁed when participation was the default. Although the framing manipulation was not signiﬁcant as a predictor of participants’ decision to receive these future notiﬁcations, the pattern of responses showed that participants in the positive framing conditions consented to receive health-related information at a higher rate than participants in the negative framing conditions (Johnson et al., 2002).
We embarked on direct well-powered replications of these two classic ﬁndings with two primary goals. First, we sought to revisit and reexamine the robustness of the basic default effect reported in the well-known organ donation decision scenario by Johnson and Goldstein (2003). Second, to build on these ﬁndings we sought to also contrast default and framing effects, replicating and extending the design used in Johnson et al. (2002).
Effect Sizes in target articles
The chosen target studies did not report effect sizes. We reanalyzed the data and conducted logistics regression analysis to calculate odds-ratios with a 95% conﬁdence interval for the regression coefﬁcients as a measure of effect size. The effect sizes of the original studies are summarized in Table 9 (for detailed results, see Table S7 and Table S8 in the supplementary materials).

Extensions
In addition to the direct replications, we also performed two extensions. First, we investigated whether the permanence of the decision affects default effects. In particular, half the study participants were told that their organ donation-related decision was valid for three years, and the other half of participants were not provided with any additional information about the permanence of their decision. We based our extension on van Dalen and Henkens (2014) who found that organ donation rates were higher when the option was temporary and would have to be renewed than when the default option was to donate. Based on these results, we investigated the presumed permanence (temporary vs. permanent) consent in Johnson and Goldstein (2003) scenario. In line with previous work, we predicted a higher organ donation participation rate when the choices were framed as temporary (i.e., the decision can be revised in ﬁve years) rather than permanent. Second, we added a conceptual replication of Johnson et al. (2002). We applied their experimental design involving framing and default effects to the organ-donation scenario in Johnson and Goldstein (2003). This replication was meant to further test the generalizability of their ﬁndings regarding the interaction of default and framing effects.

## Method

Process
We crowdsourced the replication and extension effort using two teams of two authors. Both teams were supervised by two other experienced authors. Each team worked independently to conduct their own in-depth analysis of the chosen target articles and wrote detailed pre-registrations aiming for a very close replication and adding additional extensions. Data collection was then conducted separately for each team using a different sample. Thus, the two data collections tested two independent extensions: the effect of choice permanence (Sample 1) and the conceptual replication of Experimental 2 of Johnson et al. (2002) (Sample 2).
Pre-registrations and open data/code
In both data collections, we ﬁrst preregistered the experiment on the Open Science Framework (OSF) and data collection was launched after registration. Preregistration, disclosures, power analyses, and all materials are available in the Supplementary Materials. These, together with datasets and analysis code, were
2For an action framing effect, the presentation of a scenario varies in the framing of the action (e.g., to select vs. to reject).

made available on the OSF at https://osf.io/8wd2b/. All measures, manipulations, and exclusions for this investigation are reported, and data collection was completed before analyses. Pre-registrations are available on the OSF: Group A - https://osf.io/mhwbe/, Group B - https://osf.io/j4rpc/.
Participants and power analysis
The present investigation includes two simultaneously collected data samples. For both the samples, we recruited participants from the United States via CloudResearch platform running on Amazon Mechanical Turk. Participants could participate in only one of these.
Power analyses across Group A and Group B suggested a sample size of 232. However, we note inconsistencies in the power analysis details reported as part of the pre-registrations across Group A and B. Rectiﬁed power analysis based on the original study’s results indicated that a total sample of 156 participants was sufﬁcient to obtain 95% power (at α = .05) to detect the smallest effect reported among the original studies (OR = 1.86). Please refer to the supplementary material for more details on the power analysis.
Since our replication study also involved additional extension hypotheses across two samples, we recruited 1004 and 1007 participants across two replication two teams, respectively. Additionally, a post-hoc power sensitivity analysis at an aimed sample size of 2000 participants is found to achieve a power of 96.93% power (at = .05) to detect a small effect size (i.e.,OR = 1.50). We, therefore, combined the two samples for the data analysis, which amounted to a total of 2011 participants. Following the preregistered exclusion criteria, we excluded 91 participants based on English proﬁciency, self-reported seriousness, knowledge of the hypothesis, survey completion, and place of residence (see supplementary material for details). Data were analyzed from the remaining 1920 participants (N1 = 954; N2 = 966; Mage = 38,SD = 11.85; 52% female).
Materials and Procedure
The procedure involved two parts. In the ﬁrst part, participants read about an organ donation scenario from Johnson and Goldstein (2003). In the second part, participants responded to the scenario from Experiment 2 of Johnson et al. (2002). After completing both parts of the survey, participants provided their demographic information, and they were debriefed at the end of the study. We provide a comparison of the target article sample and the replication samples in Table S2. Participants in Sample 1 were part of a choice permanence extension. In this regard, Sample 1 participants in the

ﬁrst of the experiment were randomly assigned to one of two between-participants conditions: the direct replication of Johnson and Goldstein (2003) or the temporary organ donation extension condition.
Part 1: Organ Donation
In part 1, participants were randomly assigned to 1 of 3 between-participants conditions (defaults: Opt-In vs. Opt-Out vs. No-Default). For example, participants in the “Opt-Out” condition read:
“Imagine that you have just moved to a new state and are currently ﬁlling out the required online registration forms when you are asked to indicate your organ donor status. The default in this state is that you ARE automatically enrolled to be an organ donor. You are given the choice of whether to conﬁrm or to change this status. Please select an option.”
After reading the passage, participants had to choose either “Yes - I want to be an organ donor” or “No - I do not want to be an organ donor.” In the Opt-Out condition, the “Yes” option was pre-selected. Table 1 documents the format of the display of choices across experimental conditions. So, participants who consented to organ donation just had to click “Next” at the bottom of the page, whereas participants who did not wish to be an organ donor had to click the option “No” before clicking “Next.” In the Opt-In condition, the “No” option was pre-selected. So, participants who consented to organ donation had to click the option “Yes” before proceeding, whereas participants who did not wish to be an organ donor just had to click “Next.” In the No-Default condition, participants read:
Assume you moved to a new state, therefore, you need to select enrollment as an organ donor. Please choose your preferred organ donor status:
Participants in this No-Default condition saw the same binary response options without a pre-selected default. So, they had to actively select “Yes” or “No” before clicking “Next” to proceed. After completing part 1, participants moved on to part 2.
Part 2: Survey Subscription
In part 2, participants were randomly assigned to 1 of 6 conditions in a 2 (framing: Positive vs. Negative) × 3 (default option: Opt-In vs. Opt-Out vs. No-Default) between-participants design (see Table 2 for details). At the beginning of Part 2, participants read the following instruction:
“Typically, regardless of your organ donor decision, the state online systems ask you to answer a number of health questions. Please answer the following. All the data will be kept completely conﬁdential.”

Table 1
Study stimuli for the direct replication of Johnson and Goldstein (2003) [Introduction for participants in Opt-Out/Opt-in Conditions]: Imagine that you have just moved to a new state and are currently ﬁlling out the required online registration forms when you are asked to indicate your organ donor status. The default in this state is that you ARE automatically enrolled to be an organ donor. You are given the choice of whether to conﬁrm or to change this status. Please select an option
[Opt-out]: Assume you moved to a new state in which the default is that you are an organ donor, you are therefore by default enrolled as an organ donor. Please choose your preferred organ donor status:
Yes-I want to be an organ donor
No- I do not want to be an organ donor
[Opt-in]: Assume you moved to a new state in which the default is that you are not an organ donor, you are therefore by default not enrolled as an organ donor. Please choose your preferred organ donor status:
Yes-I want to be an organ donor
No- I do not want to be an organ donor
[No-default]: Assume you moved to a new state, therefore, you need to select enrollment as an organ donor. Please choose your preferred organ donor status:
Yes-I want to be an organ donor
No- I do not want to be an organ donor
Participants then answered four generic questions on their health in general (for details, see Table S4 supplementary section). Participants then read:
“You are almost at the end of the survey. Thank you for taking part. Would you be interested in being notiﬁed about other policy/health-related surveys? (If yes, we will contact you through MTurk using your MTurk worker ID)”
Participants answered by selecting “Yes” or “No.” Each condition had a positive (“Notify me about more health surveys.”) or negative (“Do NOT notify me about more health surveys.”) framing. In positively framed

Opt-Out conditions, the ‘yes’ response was pre-selected. In positively framed Opt-In conditions, the ‘No’ response was pre-selected. In negatively framed Opt-Out conditions, the ‘No’ response was pre-selected. In negatively framed Opt-in conditions, the ‘yes’ response was preselected.
Extensions
Extension 1: The effect of choice permanence. Participants in Sample 1 were part of the choicepermanence extension. As such, participants in Sample 1 were randomly assigned to one of two betweenparticipants conditions (temporary or permanent). Participants assigned to the temporary conditions took the same survey as those in the permanent conditions—only they received the following additional instruction at the beginning of part 1 of the study: “Please note: Your organ donor authorization, if granted, would be for 3 years only, meaning that after 3 years you will be asked to reconﬁrm your organ donor decision.” Participants in the permanent conditions had no additional instructions. Extension 2: Conceptual replication of Experimental 2 of Johnson et al. (2002). All the participants in Sample 2 took part in a different extension. Immediately after completing Part 1 of the study but just before Part 2, participants read the following instructions (see Table 3 for details): “Would you like to receive further information about organ donation through MTurk? If you indicate your approval, we’ll contact you through MTurk using your worker ID with further information about organ donation.” These participants were randomly assigned to 1 of 6 conditions in a 2 (framing: Positive vs. Negative) times 3 (default option: Opt-Out vs. Opt-In vs. No-Default) between-participants design (for details, see Table S6 in the supplementary section). After reading the above instruction, participants selected “Yes” or “No” to a question asking for consent to receiving further information on organ donation. Each of the default conditions involved either a positive (“Send me more information about organ donation”) or negative (“Do NOT send me more information about organ donation”) framing. The responses were pre-selected in the Opt-In and Opt-Out default conditions mirroring the experimental design of Experiment 2 of Johnson et al. (2002). In positively framed Opt-Out conditions, the ‘yes’ response was preselected. In positively framed Opt-In conditions, the ‘No’ response was pre-selected. In negatively framed Opt-Out conditions, the ‘no’ response was pre-selected.

Table 2
Study stimuli for the direct replication of Johnson et al. (2002) [Introduction]: Typically, regardless of your organ donor decision, the state online systems ask you to answer a number of health questions. Please answer the following. All the data will be kept completely conﬁdential.
You are almost at the end of the survey. Thank you for taking part. Would you be interested in being notiﬁed about other policy/health-related surveys? (If yes, we will contact you through MTurk using your MTurk worker ID) [Positive frame, Opt-out]: Notify me about more health surveys.
Yes
No
[Positive frame, Opt-in]: Notify me about more health surveys.
Yes
No
[Positive frame, No-default]: Notify me about more health surveys.
Yes
No
[Negative frame, Opt-out]: Notify me about more health surveys.
Yes
No
[Negative frame, Opt-in]: Do NOT notify me about more health surveys.
Yes
No
[Negative frame, No-default]: Notify me about more health surveys.
Yes
No

### Table 2
*Study stimuli for the direct replication of Johnson et al. (2002) [Introduction]: Typically, regardless of your organ donor decision, the state online systems ask you to answer a number of health questions. Please answer the following. All the data will be kept completely conﬁdential.*

<table>
  <thead>
    <tr>
      <th>Table 2</th>
      <th>In negativelyframed Opt-In conditions,the‘yes’re-<br>sponse was pre-selected.</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Study stimulifor the direct replication of Johnson et al.</td>
      <td></td>
    </tr>
    <tr>
      <td>(2002)</td>
      <td>Data Transformations</td>
    </tr>
    <tr>
      <td>[Introduction]:</td>
      <td></td>
    </tr>
  </tbody>
</table>

## Results

We provide a summary of the ﬁndings in Table 9. We present complete descriptive statistics across the two samples in Table 5 (also see Table S10 in the supplementary materials).

### Table 3
*Table 4 Study stimuli for the on conceptual replication of Johnson et al. (2002) [Introduction]: Typically, regardless of your organ donor decision, the state online systems ask you to answer a number of health questions. Please answer the following.*

<table>
  <thead>
    <tr>
      <th>Table 3</th>
      <th>Table 4</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Study stimuli for the on conceptual replication of Johnson</td>
      <td>Table 4. Classiﬁcation of replications based on LeBel et al.</td>
    </tr>
    <tr>
      <td>et al. (2002)</td>
      <td>(2019)<br>Design facetReplication study</td>
    </tr>
    <tr>
      <td>[Introduction]:</td>
      <td>IV operationalizationSame</td>
    </tr>
    <tr>
      <td>Typically,regardless of your organ donor decision,the</td>
      <td>DV operationalizationSame</td>
    </tr>
    <tr>
      <td>state online systems ask you to answer a number of</td>
      <td>IV stimuliSame</td>
    </tr>
    <tr>
      <td>health questions. Please answer the following. Allthe</td>
      <td>DV stimuliSame</td>
    </tr>
    <tr>
      <td>data will be kept completely conﬁdential.</td>
      <td>Procedural detailsSimilar<br>Physical settingsDifferent</td>
    </tr>
    <tr>
      <td>You are almost atthe end ofthe survey.Thank you</td>
      <td>Contextual variablesDifferent</td>
    </tr>
  </tbody>
</table>

Part 1: Replication of Johnson and Goldstein (2003)
Consistent with the original study, participants in the Opt-Out condition consented to organ donation at a higher rate (73.5%) than participants in the Opt-In condition (62.5%) (Chi-squared test: χ2(1) = 12.96, p<.001, Odds ratio (OR) = 1.67, 95% CI [1.27, 2.19] (see Figure 1). This result was consistent across both samples (See Table S11 for complete results). Also, participants in the No-Default condition consented to organ donation at a higher rate (69.7%) than participants in the Opt-In condition (62.5%) (χ2(1) = 5.31, p =.021, OR = 1.38, 95% CI [1.06, 1.80]) with slight deviations between the two samples (See Table S11 for complete results). Also see Table 6 for the results based on logistic regression.
Part 2: Replication of Johnson, Bellman, and Lohse (2002)
We present the results of the regression analysis in Table 7 (Figure 2), and descriptive statistics in Table S9 in the supplementary section.
Default effects
We failed to ﬁnd support for differences in rates of consent to receive health-related information between the Opt-Out condition (60.5%) and the Opt-In condition (61.1%) (b = -.29, p = .095, OR = 0.75, 95% CI [0.53, 1.05]); that is, we found no support for a default effect. This result was consistent across both samples (See Table S11 for complete results). Participants in the No-Default (59.8%) condition, moreover, consented to receive health-related information at a lower rate than participants in Opt-In (61.1%) condition (b = -0.41, p = .021, OR = 0.67, 95% CI [0.47, 0.94]).

### Table 5
*Descriptive table of the participation rates. Replication Study Replication of Experiment 1 from Johnson & Goldstein (2003) Replication of Experiment 2 from Johnson, Bellman & Lohse (2002) Note. N = 1920.*

<table>
  <thead>
    <tr>
      <th>Table 5</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Descriptive table of the participation rates.</td>
      <td></td>
      <td></td>
      <td></td>
      <td>Combined replication sample</td>
    </tr>
    <tr>
      <td>Replication Study</td>
      <td>Experimental Conditions<br>Opt-in default</td>
      <td></td>
      <td>n<br>488</td>
      <td>Participation rate<br>62.5%</td>
    </tr>
    <tr>
      <td>Replication of Experiment 1 from Johnson &amp; Goldstein (2003)</td>
      <td>Opt-out default<br>No-default (no default)<br>Opt-in default</td>
      <td>Positive Framing<br>Negative Framing<br>Positive Framing</td>
      <td>476<br>482<br>324<br>324<br>321</td>
      <td>73.5%<br>69.7%<br>88.6%<br>33.6%<br>93.1%</td>
    </tr>
    <tr>
      <td>Replication of Experiment 2 from Johnson, Bellman &amp; Lohse (2002)</td>
      <td>Opt-out default<br>No-default (no default)</td>
      <td>Negative Framing<br>Positive Framing<br>Negative Framing</td>
      <td>319<br>320<br>312</td>
      <td>27.6%<br>93.4%<br>25.3%</td>
    </tr>
    <tr><td colspan="5"><strong>Note. N = 1920.</strong></td></tr>
  </tbody>
</table>

27.6%

93.4%

25.3%

### Table 6
*Summary of the replication results of Part 1 (Johnson and Goldstein (2003)) based on logistic regression analysis Predictor Estimate SE Z p OR [95% CI] Intercept 0.51 0.09 5.46 <.001 1.67 [1.39, 2.00] Default: No-Default – Opt-In 0.32 0.14 2.37 0.018 1.38 [1.06, 1.80] Default: Opt-Out – Opt-In 0.51…*

<table>
  <thead>
    <tr>
      <th>Default: Opt-Out – Opt-In</th>
      <th>0.51</th>
      <th>0.14</th>
      <th>3.65</th>
      <th>&lt;.0011.67 [1.27, 2.19]</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Note. Estimates represent the odds of the dependent variable = “1” vs. “0”.</td>
      <td></td>
      <td></td>
      <td></td>
      <td>Framing effects</td>
    </tr>
  </tbody>
</table>

Figure 1



of direct replications of Johnson and Goldstein (2003). Percentage of participants consenting to organ donation by condition across both samples. Note.* p < .05, ** p< .01, *** p < .001

Framing effects
Participants in the positive framing condition consented to receive health-related information (91.7%) at a higher rate than participants in the negative framing condition (28.9%) (b= 2.74, p < .001, OR = 15.61, 95% CI [10.31, 23.63]).
Exploratory: Default effects as a function of frames
We proceeded to conduct additional exploratory (not preregistered) analyses examining the interaction between framing and defaults. We found support for an interaction (see Table 7). We considered two sets of interactions: 1) (Positive – Negative) times (No-default – Opt-In); 2) (Positive – Negative) times (Opt-Out – OptIn).
For the (Positive – Negative) × (No-default – OptIn) interaction, we looked at the consent rates between the No-Default and Opt-In conditions across the positive and negative frame (b = 1.01, p = .003, OR = 2.76, 95% CI [1.43, 5.32]). Within positive framing conditions, participants in the No-Default condition (93.4%) consented to receive health-related information at a higher rate than participants in the Opt-In condition (88.6%) (see Table S12 and Table S13 in the supplementary materials). The pattern of results was in the opposite direction in the negative framing conditions: participants in the No-Default condition (25.3%) consented to receive health-related information at a lower rate than participants in the Opt-In condition (33.6%).

The results were similar for the (Positive – Negative) times (Opt-Out – Opt-In) interaction (b = 0.85, p = .010, OR = 2.35, 95% CI [1.23, 4.49]). Within positive framing conditions, participants in the Opt-Out condition (93.1%) consented to receive health-related information at a higher rate than participants in the Opt-In condition (88.6%). The pattern of results was in the opposite direction within the negative framing conditions: participants in the Opt-Out condition (27.6%) consented to receive health-related information at a lower rate than participants in the Opt-In condition (33.6%).
Extensions
Extension 1: Temporary vs. Permanent Choice
We found no evidence that organ donation rates varied between the temporary (70.3%) and the permanent conditions (65.8%) (χ2 (1, N = 954) = 1.94, p = .163; d = 0.11, 95% CI [-0.04, 0.26]; Figure 3). Additionally, we looked at differences within the No-Default condition, and again failed to ﬁnd evidence for differences (temporary: 74.7%; permanent: 67.3%; χ2 (1, N = 320) = 1.78, p = .182, d = 0.20, 95% C.I. [-0.07, 0.47]).
Extension 2: Conceptual replication of Experimental 2 of Johnson et al. (2002)
We summarized the regression analysis in Table 8 and Figure 4, and descriptive statistics are provided in Table S14 in the supplementary.
Participants in the Opt-Out condition consented to receive organ donation-related information (50.2%) at a higher rate than participants in Opt-In condition (37.3%) (b = 0.59; p = .012, OR = 1.81, 95% CI [1.14, 2.87]). We found no evidence that consent rate varied between participants in the No-Default condition (46.6%) and participants in the Opt-In condition (37.3%) (b = 0.39; P = .092, OR = 1.48, 95% CI [0.94, 2.32]). Participants in the positive framing condition consented to receive organ donation-related information (24.9%) at a lower rate than participants in negative framing condition (64.6%) (b= 1.82; p < .001, OR = 0.16, 95% CI [0.10, 0.27]). We found no evidence that results of defaults on participation rate vary as a function of frame (see Table 8).
Summary of replication ﬁndings
We replicated the default effects from Johnson and Goldstein (2003). In Part 1 of our study, participants consented to donate their organs at a higher rate when they had to opt out relative to when they had to opt in. We, however, failed to replicate the default effects

in Johnson et al. (2002). In Part 2 of our study, we found no evidence that consent to be notiﬁed about health-related surveys varied between the opt-out and opt-in conditions. Furthermore, we found that people in positively framed scenarios consented to receive healthrelated information at a higher rate than participants in negatively framed scenarios. This result deviated from the ﬁndings of Johnson et al. (2002) that showed no framing effects.
We followed LeBel et al.’s (2019) framework for the evaluation of our replication using three factors: (a) whether a signal was detected (i.e., the conﬁdence interval for the replication Effect Size (ES) excludes one), (b) consistency of the replication ES with the original study’s ES, and (c) precision of the replication’s ES estimate (see Figure S2 in the supplementary material). We summarized our evaluations of the replications’ ﬁndings based on LeBel et al.’s (2019) replication evaluation framework in Table 9 (see Figure 5).
Extensions: Summary of ﬁndings
In the ﬁrst extension, we predicted that people would be more inclined to become donors when consent to organ donation is temporary. We found no evidence that consent varied between the temporary and permanent conditions.
In the second extension, we conducted a conceptual replication of Experiment 2 of Johnson et al. (2002) using the scenario from Part 1 in which participants consented to receive additional information about organ donation. We found support for the default effect: participants who had to opt out consented at higher rates than those who had to opt in. Deviating from the original study where they found no support for framing effects, we found that people in positively framed scenarios consented to receive health-related information at a lower rate than participants in negatively framed scenarios. Framing effects in our extension is opposite to those found in our direct replication of the original study scenario (Johnson et al. 2002).
Summary of ﬁndings of Johnson et al. (2002) across original, direct replication, and conceptual replication studies
The ﬁndings across direct and conceptual replication of Johnson et al. (2002) provide mixed support to the original study’s assertion. We summarize the comparison of the ﬁndings in Table 10. Both direct and conceptual replication failed to ﬁnd differences in consent rates between the No-Default condition and the Opt-In condition. Only the conceptual replication found that consent rates were higher in Opt-out condition than in the Opt-In condition. Regarding the framing effects, we

### Table 7
*Summary of the replication results of Part 1 (Johnson Goldstein, 2003) based on logistic regression analysis*

```
Predictor
Estimate
Model 1
Z
p
OR [95% CI] Estimate
Model 2
Z
p
OR [95% CI]
```

Intercept Framing: Positive – Negative Default: No-Default – Opt-In Default: Opt-Out – Opt-In Interaction term: (Positive – Negative) × (No-Default–Opt-In) (Positive – Negative) × (Opt-Out –Opt-In)

0.51 [0.40, 0.64] 15.30 [10.23, 23.40]
0.66 [0.47, 0.94] 0.75 [0.54, 1.05]
2.74 [1.43, 5.35] 2.33 [1.23, 4.49]

Note. Estimates represent the odds of the dependent variable = “1” vs. “0”. Standard errors are reported within the brackets.

Table 8

Summary of the replication results of Extension 2 (conceptual replication of Johnson et al. (2002) based on logistic

regression analysis

Predictor
Intercept Framing: Positive – Negative Default: No-Default – Opt-In Default: Opt-Out – Opt-In Interaction terms: (Positive – Negative) × (No-Default–Opt-In) (Positive – Negative) × (Opt-Out –Opt-In)

OR [95% CI] 1.33 [0.97, 1.81] 0.16 [0.09, 0.27] 1.48 [0.94, 2.32] 1.80 [1.14, 2.86]
1.20 [0.59, 2.41] 1.07 [0.53, 2.17]

Note. Estimates represent the odds of the dependent variable = “1” vs. “0”; N = 966. Standard errors are reported within the

brackets.

Table 9

Summary and comparison of ﬁndings of the current replication study and the target studies

Part Part 1: Johnson and Goldstein (2003) *
Part 2: Johnson et al. (2002)

Target effect Default effects: No-Default vs. Opt-In Default effects: Opt-Out vs. Opt-In Default effects: No-Default vs. Opt-In Default effects: Opt-Out vs Opt-In Framing effects: Positive vs. Negative

Original effect size 4.72 [2.03 , 10.96] 5.93 [2.48 , 14.20] 3.29 [1.28, 8.45] 4.31 [1.62, 11.46] 1.86 [0.76, 4.57]

Replication effect size 1.38 [1.06 , 1.80] 1.67 [1.27 , 2.19] 0.66 [0.47, 0.94] 0.75 [0.53, 1.05] 15.30 [10.23, 23.40]

Replication summary Signal-inconsistent, smaller Signal-inconsistent, smaller Signal-inconsistent, opposite No signal-inconsistent Signal-inconsistent, stronger

Note. Replication summary based on the criteria by LeBel et al. (2019). (*) The effect size [Odds ratio] for this target study was

calculated based on 2-sample test for equality of proportions.

Table 10

Summary of the ﬁndings of Johnson et al. (2002) across original, direct replication, and conceptual replication studies

Predictor
Default condition: No-Default– Opt-In Opt-Out – Opt-In Framing condition: Positive – Negative

Note. Directionality dimension summarizes the directional consistency of results across Default effects and Framing effects; Predicted directionality of framing effects: participants’ consent rates are higher in the positive frame than negative frame condition; Predicted directionality of default effects: consent rates are higher in ‘Opt-Out’ and ‘No-Default’ experimental condition than ‘Opt-In’ experimental condition. Signal, indicates support for the hypothesis using null hypothesis signiﬁcance testing ( p < .05)

Figure 2



of direct replication of Johnson et al. (2002). Percentage of participants who agreed to be notiﬁed about healthrelated surveys in the future. (A) Percentage of participants participating in the health survey by frame. (B) Percentage of participants participating in the health survey by default conditions. (C) Percentage of participants participating in the health survey by frame and conditions.

Figure 3



of Extension 1. Percentage of participants who consented to organ donation between permanent vs. temporary choice scenarios. Note.* p < .05, ** p< .01, *** p < .001

expected to ﬁnd that participants in the positive framing condition consent at a higher rates than participants in the negative framing condition. While the original study did not ﬁnd this, we found that consent rates were higher in positive frame condition than negative frame condition in our direct replication. However, in our conceptual replication, we found a framing effect in the opposite direction.

## General discussion

We conducted a direct, close replication of Johnson and Goldstein (2003) and Johnson et al. (2002). In Part 1 of our study, we successfully replicated Johnson and Goldstein (2003). Participants consented to be organ donors at higher rates when they had to opt out of consent relative to participants who had to opt in. We found that participants in the No-Default condition—where no response was pre-selected—consented to organ donation at higher rates relative to participants who had to opt in. Additionally, we found that the permanence of these decisions affected people’s choices.
Our replication results are consistent with Johnson and Goldstein (2003)—though the effects were smaller than those reported in the original study. The weaker effect is in line with recent work which found that effect sizes in large-scale studies were smaller than the estimates forecasted by academic experts and practitioners with relevant knowledge of nudge effects (DellaVigna

Figure 4
Extension 2: Percentage of participants who agreed to be notiﬁed about further information about organ donation in the future. (A) Participation rates by frame. (B) Participation rates by default conditions. (C) Participation rates by frame and conditions.

and Linos, 2022). Our well-powered study provides a more precise estimation of the effect size (OR = 1.67, 95% CI [1.27, 2.19]) that may be useful for future metaanalyses and for policy applications.
In Part 2 of our study, our replication results of Johnson et al. (2002) were inconsistent with the original ﬁndings. Unlike the original study, we found framing effects, yet we found no evidence for default effects. Consistent with the original study, we found that participants in the positive framing conditions consented to receive organ donation information at a higher rate than participants in the negative framing condition. However, in our conceptual replication of Johnson et al. (2002) that we report as Extension 2, participants in the positive framing condition consented to receive organ donation information at a lower rate than participants in the negative framing condition.
Our results on default effects were inconsistent with the original ﬁndings in Johnson et al. (2002): we had no evidence for default effects overall. Nonetheless, we did ﬁnd some indication of default effects when scenarios were framed positively. For instance, within positive framing conditions, participants in the No-Default condition and Opt-Out condition consented to receive health-related information at a higher rate than participants in the Opt-In condition. The pattern of results was in the opposite direction within the negative framing conditions: participants in the No-Default condition and Opt-Out condition consented to receive health-

related information at a lower rate than participants in Opt-In condition. Interestingly, we found the consistent pattern across positive and negative frames in the conceptual replication: although these differences were not signiﬁcant, participants in the No-Default condition and Opt-Out condition consented to receive organ donation related information at a higher rate than participants in Opt-In condition. As such, our results suggest that the stability of default effects can vary depending on the framing of the decision scenario.
There are several possible explanations for the inconsistent ﬁndings in our replications of Johnson et al. (2002). First, the failure to replicate the default effects may have been due to insufﬁcient sample size in Johnson et al. (2002), which involved only 235 participants—–about 39 participants for each experimental condition. This small sample may have led to false-positive results and inﬂated the effect size. Moreover, the smaller sample size in the original article may have resulted in the failure to detect the framing effects and the interaction that we found.
Second, the differences could be a result of changing preferences toward participating in online surveys. The original study was published in 2002, and the experimental scenario involved consenting to be notiﬁed about health-related surveys in the near future. People’s preferences for taking part in online surveys may have changed in the last two decades. Therefore, the differences in the results could be informed by the change in

Figure 5
Effect sizes in Johnson and Goldstein (2003), Johnson et al. (2002), and the current replication. Estimates and conﬁdence intervals are plotted on a natural logarithmic scale.

peoples’ preferences. Given the other successful replication in Part 1 of our study, we think this explanation is unlikely, yet we cannot rule out this possibility.
A third related explanation may be due to carry-over effects resulting from the order of the replications. The failed replication of Johnson et al. (2002) was in Part 2 and followed the unrelated organ-donation scenario in Part 1. We acknowledge that there is the slight possibility that somehow the order of execution affected the ﬁndings in Part 2. We consider this unlikely; the ﬁndings were not noise—–they reﬂected a clear pattern of framing effects over default effect—–so it would seem improbable that the slight manipulation in Part 1 triggered such a major shift from default effects to framing effects in Part 2. In our study design, we also took measures to mitigate carry-over effects. In Part 1, participants responded to the organ donation scenarios of Johnson and Goldstein (2003). The participants were assigned to three between-participants scenarios: OptOut, Opt-in, No-default. After completing Part 1 of the experiment, participants were randomly assigned to one

of six between-participants conditions related to Johnson et al. (2002) in Part 2. So, we ﬁnd it unlikely that a carry-over effect occurred in such a complex betweenparticipants design. Furthermore, Samples 1 and 2 had slightly different procedures. Despite these differences, we report similar results across the sample (see Table S11 in the supplementary materials). Therefore, this possibility of carry-over effects is unlikely.
Finally, the lack of support for the default effects in the negatively framed scenarios of Johnson et al. (2002) may have been due to the fact that double-negatively framed questions (i.e., negatively framed in the Opt-in scenario) are more confusing to participants than the other conditions. However, this possibility too seems to be an unlikely explanation for the lack of default effects. First off, the original study carried the same double-negatively framed questions yet found support for default effects. While we recognize that doublenegative questions may have been taxing to follow, the relatively consistent effects within negatively framed default conditions suggest otherwise. Across the three

conditions with negatively-framed descriptions, the participation rates were similar: Opt-Out (28%), Opt-In (34%), and No-Default (25%). The similar participation rates across default conditions within the negative frame suggest that comprehending double negatively framed questions do not explain our pattern of ﬁndings.
There are also some potential explanations for other inconsistencies we found in our replications. Interestingly, the direction of framing effects in our conceptual replication of Johnson et al. (2002) was in the opposite direction of that found in our direct replication of Johnson et al. (2002). Although this result is inconsistent with the original study, it may not be entirely surprising; previous work suggests that framing effects may vary across task contexts. For example, work by Zhen and Yu (2016) show that framing effect vary between vignette-based vs. reward-based decision tasks. Furthermore, previous work also found that the direction of framing effects may differ based the relative attractiveness of the alternatives (Chandrashekar et al., 2021; Chen and Proctor, 2017; Wedell, 1997), or the degree to which decision may have personal relevance to participants (Krishnamurthy et al., 2001). Future work on framing effects may further investigate whether different task contexts modulate the direction of framing effects.
At a more theoretical level, Wedell (1997) accentuation hypothesis perhaps best describes the pattern of current results about framing effects. Wedell (1997) argues that people have a higher need for justiﬁcation in a positively framed choice than in a negatively framed choice. This higher need for justiﬁcation highlights the differences between alternatives. On this account, when the overall attractiveness or beneﬁts of participating in a health survey is high, people in the positively framed choice will choose to participate at a higher rate. Alternatively, when the overall attractiveness of participating in a health survey is lower, participants in the positively framed choice will choose to participate at a lower rate. Our results across direct and conceptual replication of Johnson et al. (2002) support this account. In the direct replication of Johnson et al. (2002) using a healthcare survey scenario, we ﬁnd an overall high participation rate of 60.4% across conditions, and we found that participation rates were higher in the positive frame condition. In the conceptual replication of Johnson et al. (2002) that involved an organ donation scenario, we found an overall lower participation rate of 44.6% across experimental conditions, suggesting that the overall attractiveness of the option of consenting to receive additional information on organ donation is lower. Interestingly, we found that participation rates were lower in the positively framed condition. Our ﬁnd-

ings suggest that future work on the default effect may beneﬁt from paying closer attention to the accentuation hypothesis.

## Conclusion

Overall, our effort to replicate Johnson et al. (2002) contributes to the extant literature by testing the stability of default effects. Since the publication of Johnson et al. (2002), there has not been much interest in further studying framing effects (Positive vs. Negative frame) together with default effects. We believe that our ﬁndings indicate that this is a promising area for future research.
The current ﬁndings underline the importance of well-powered preregistered replications and extensions of notable ﬁndings in the judgment and decisionmaking literature. Our results suggest that the stability of default effects depends on the framing and context of the decision scenario and therefore hold valuable implications for the study of default effects. Although work on default effects has deservedly garnered attention from both scholars and public policy practitioners in the last two decades, our work suggests that we need a more reﬁned and contextualized understanding of defaults’ effectiveness.
We propose two main assertions. First, the effect size of default effects is likely smaller than those documented in original studies (DellaVigna and Linos, 2022. Therefore, we need well-powered samples to study default effects to achieve greater precision in our effect size estimates. Second, framing seems to inﬂuence the direction of default effects. Future work on default effects should be aware that people’s decision frame can inﬂuence defaults’ effectiveness. We hope the current replication opens up a range of theoretical and empirical work that can further future work on default effects.

## Acknowledgement

We would like to thank Ignazio Ziano and Jieying Chen for their feedback reviewing initial drafts of this project.

Conﬂict of Interest and Funding
This research was supported by the European Association for Social Psychology seedcorn grant.

## Author Contributions

Nadia Adelina, Shiyuan Zeng, Yan Ying Esther Chiu, and Grace Yat-Sum Leung analyzed the original articles, wrote the pre-registrations, designed the replications and the extensions, and conducted an initial analysis of the results and write-up of the ﬁrst draft. Boley Cheng guided and assisted the replication effort. Subramanya Prasad Chandrashekar and Paul Henne veriﬁed and extended analyses, integrated the studies, and wrote the ﬁnal manuscript for submission. Gilad Feldman led the replication efforts, supervised each step, conducted the pre-registrations, ran data collections, provided feedback throughout, and edited the ﬁnal manuscript for submission.
Open Science Practices
This article earned the Preregistration+, Open Data and the Open Materials badge for preregistering the hypothesis and analysis before data collection, and for making the data and materials openly available. It has been veriﬁed that the analysis reproduced the results presented in the article. The entire editorial process, including the open reviews, is published in the online supplement.

## References

Abadie, A., & Gay, S. (2006). The impact of presumed consent legislation on cadaveric organ donation: A cross-country study. Journal of Health Economics, 25(4), 599–620. https : / / doi . org / 10.1016/j.jhealeco.2006.01.003
Abhyankar, P., Summers, B. A., Velikova, G., & Bekker, H. L. (2014). Framing options as choice or opportunity: Does the frame inﬂuence decisions? [Publisher: Sage Publications Sage CA: Los Angeles, CA]. Medical Decision Making, 34(5), 567–582.
Araña, J. E., & León, C. J. (2013). Can Defaults Save the Climate? Evidence from a Field Experiment on Carbon Offsetting Programs. Environmental and Resource Economics, 54(4), 613–626. https: //doi.org/10.1007/s10640-012-9615-x

Benartzi, S., & Thaler, R. H. (1999). Risk aversion or myopia? Choices in repeated gambles and retirement investments [Publisher: INFORMS]. Management science, 45(3), 364–381.
Bohner, G., & Schlüter, L. E. (2014). A Room with a Viewpoint Revisited: Descriptive Norms and Hotel Guests’ Towel Reuse Behavior [Publisher: Public Library of Science]. PLOS ONE, 9(8), e104086. https : / / doi . org / 10 . 1371 / journal . pone.0104086
Brewer, M. B., & Kramer, R. M. (1986). Choice behavior in social dilemmas: Effects of social identity, group size, and decision framing [Place: US Publisher: American Psychological Association]. Journal of Personality and Social Psychology, 50, 543–549. https://doi.org/10.1037/ 0022-3514.50.3.543
Brown, C. L., & Krishna, A. (2004). The skeptical shopper: A metacognitive account for the effects of default options on choice. Journal of consumer research, 31(3), 529–539.
Chandrashekar, S. P., Weber, J., Chan, S. Y., Cho, W. Y., Chu, T. C. C., Cheng, B. L., & Feldman, G. (2021). Accentuation and compatibility: Replication and extensions of Shaﬁr (1993) to rethink choosing versus rejecting paradigms [Publisher: Cambridge University Press]. Judgment and Decision Making, 16(1), 36–56.
Chen, J., & Proctor, R. W. (2017). Role of accentuation in the selection/rejection task framing effect [Place: US Publisher: American Psychological Association]. Journal of Experimental Psychology: General, 146, 543–568. https : / / doi . org/10.1037/xge0000277
Cronqvist, H., & Thaler, R. H. (2004). Design choices in privatized social-security systems: Learning from the Swedish experience [Publisher: American Economic Association]. American Economic Review, 94(2), 424–428.
De Martino, B., Kumaran, D., Seymour, B., & Dolan, R. J. (2006). Frames, biases, and rational decisionmaking in the human brain [Publisher: American Association for the Advancement of Science]. Science, 313(5787), 684–687.
DellaVigna, S., & Linos, E. (2022). RCTs to scale: Comprehensive evidence from two nudge units [Publisher: Wiley Online Library]. Econometrica, 90(1), 81–116.
Ebeling, F. (2013). Non-binding defaults and voluntary contributions to a public good—clean evidence from a natural ﬁeld experiment (working paper no: 66).

English, V., Johnson, E., Sadler, B. L., & Sadler, A. M. (2019). Is an opt-out system likely to increase organ donation? [Publisher: British Medical Journal Publishing Group]. British Medical Journal, 364. https : / / doi . org / https : //doi.org/10.1136/bmj.l967
Evans, A. M., Dillon, K. D., Goldin, G., & Krueger, J. I. (2011). Trust and self-control: The moderating role of the default [Publisher: Cambridge University Press]. Judgment and Decision Making, 6(7), 697–705. https : / / doi . org / 10 . 1017 / S1930297500002709
Everett, J. A., Caviola, L., Kahane, G., Savulescu, J., & Faber, N. S. (2015). Doing good by doing nothing? the role of social norms in explaining default effects in altruistic contexts. European Journal of Social Psychology, 45(2), 230–241.
Fagley, N. S., & Miller, P. M. (1987). The effects of decision framing on choice of risky vs certain options [Publisher: Elsevier]. Organizational Behavior and Human Decision Processes, 39(2), 264–277. https : / / doi . org / https : / / doi . org / 10.1016/0749-5978(87)90041-0
Ferguson, C. J., & Heene, M. (2012). A vast graveyard of undead theories: Publication bias and psychological science’s aversion to the null [Publisher: Sage Publications Sage CA: Los Angeles, CA]. Perspectives on Psychological Science, 7(6), 555–561. https : / / doi . org / 10 . 1177 / 1745691612459059
Franco, A., Malhotra, N., & Simonovits, G. (2014). Publication bias in the social sciences: Unlocking the ﬁle drawer [Publisher: American Association for the Advancement of Science]. Science, 345(6203), 1502–1505. https : / / doi . org / 10 . 1126/science.1255484
Gamliel, E., & Kreiner, H. (2013). Is a picture worth a thousand words? The interaction of visual display and attribute representation in attenuating framing bias [Publisher: Cambridge University Press]. Judgment and Decision Making, 8(4), 482–491. https : / / doi . org / 10 . 1017 / S1930297500005325
Grifﬁths, L. (2013). Human Transplantation (Wales) Act 2013.
Halpern, D. (2015). Inside the nudge unit: How small changes can make a big difference. Random House.
Huber, V. L., Neale, M. A., & Northcraft, G. B. (1987). Decision bias and personnel selection strategies. Organizational Behavior and Human Decision Processes, 40(1), 136–147. https : / / doi . org/10.1016/0749-5978(87)90009-4

Huh, Y. E., Vosgerau, J., & Morewedge, C. K. (2014). Social defaults: Observed choices become choice defaults. Journal of Consumer Research, 41(3), 746–760.
Jachimowicz, J. M., Duncan, S., Weber, E. U., & Johnson, E. J. (2019). When and why defaults inﬂuence decisions: A meta-analysis of default effects. Behavioural Public Policy, 3(2), 159–186.
Johnson, E. J., & Goldstein, D. (2003). Do Defaults Save Lives? Science, 302(5649). https://doi.org/10. 1126/science.1091721
Johnson, E. J., Bellman, S., & Lohse, G. L. (2002). Defaults, Framing and Privacy: Why Opting InOpting Out1. Marketing Letters, 13(1), 5–15. https://doi.org/10.1023/A:1015044207315
Johnson, E. J., Hershey, J., Meszaros, J., & Kunreuther, H. (1993). Framing, probability distortions, and insurance decisions. Journal of Risk and Uncertainty, 7(1), 35–51. https : / / doi . org / 10 . 1007/BF01065313
Kahneman, D. (2003). Maps of Bounded Rationality: Psychology for Behavioral Economics. American Economic Review, 93(5), 1449–1475. https : / / doi.org/10.1257/000282803322655392
Keller, P. A., Harlam, B., Loewenstein, G., & Volpp, K. G. (2011). Enhanced active choice: A new method to motivate behavior change. Journal of Consumer Psychology, 21(4), 376–383. https://doi. org/10.1016/j.jcps.2011.06.003
Kettle, S., Hernandez, M., Sanders, M., Hauser, O., & Ruda, S. (2017). Failure to CAPTCHA Attention: Null Results from an Honesty Priming Experiment in Guatemala [Number: 2 Publisher: Multidisciplinary Digital Publishing Institute]. Behavioral Sciences, 7(2), 28. https://doi.org/ 10.3390/bs7020028
Kramer, R. M. (1989). Windows of vulnerability or cognitive illusions? Cognitive processes and the nuclear arms race. Journal of Experimental Social Psychology, 25(1), 79–100. https://doi.org/10. 1016/0022-1031(89)90040-1
Krishnamurthy, P., Carter, P., & Blair, E. (2001). Attribute Framing and Goal Framing Effects in Health Decisions. Organizational Behavior and Human Decision Processes, 85(2), 382–399. https://doi.org/10.1006/obhd.2001.2962
Kristal, A. S., Whillans, A. V., Bazerman, M. H., Gino, F., Shu, L. L., Mazar, N., & Ariely, D. (2020). Signing at the beginning versus at the end does not decrease dishonesty [Publisher: Proceedings of the National Academy of Sciences]. Proceedings of the National Academy of Sciences, 117(13),

7103–7107. https : / / doi . org / 10 . 1073 / pnas . 1911695117 Kruglanski, A. W., & Gigerenzer, G. (2011). Intuitive and deliberate judgments are based on common principles [Place: US Publisher: American Psychological Association]. Psychological Review, 118, 97–109. https://doi.org/10.1037/ a0020762 Kühberger, A. (1998). The Inﬂuence of Framing on Risky Decisions: A Meta-analysis. Organizational Behavior and Human Decision Processes, 75(1), 23–55. https://doi.org/10.1006/obhd. 1998.2781 Kvarven, A., Strømland, E., & Johannesson, M. (2020). Comparing meta-analyses and preregistered multiple-laboratory replication projects [Number: 4 Publisher: Nature Publishing Group]. Nature Human Behaviour, 4(4), 423–434. https : //doi.org/10.1038/s41562-019-0787-z LeBel, E. P., Vanpaemel, W., Cheung, I., & Campbell, L. (2019). A Brief Guide to Evaluate Replications. Meta-Psychology, 3. https://doi.org/10.15626/ MP.2018.843 Levin, I. P., & Gaeth, G. J. (1988). How consumers are affected by the framing of attribute information before and after consuming the product [Place: US Publisher: Univ of Chicago Press]. Journal of Consumer Research, 15, 374–378. https://doi. org/10.1086/209174 Li, J., & Nikolka, T. (2016). The effect of presumed consent defaults on organ donation [Publisher: München: ifo Institut-Leibniz-Institut für Wirtschaftsforschung an der . . . ]. CESifo DICE Report, 14(4), 90–94. Madden, S., Collett, D., Walton, P., Empson, K., Forsythe, J., Ingham, A., Morgan, K., Murphy, P., Neuberger, J., & Gardiner, D. (2020). The effect on consent rates for deceased organ donation in Wales after the introduction of an optout system [Publisher: Wiley Online Library]. Anaesthesia, 75(9), 1146–1152. https : / / doi . org/10.1111/anae.15055 Madrian, B. C., & Shea, D. F. (2001). The Power of Suggestion: Inertia in 401(k) Participation and Savings Behavior*. The Quarterly Journal of Economics, 116(4), 1149–1187. https://doi.org/ 10.1162/003355301753265543 McKenzie, C. R., Liersch, M. J., & Finkelstein, S. R. (2006). Recommendations implicit in policy defaults. Psychological Science, 17(5), 414–420. Mintz, A., & Redd, S. B. (2003). Framing Effects in International Relations. Synthese, 135(2), 193–213. https://doi.org/10.1023/A:1023460923628

Nacion, L. (2005). El Senado aprobó la ley del donante presunto. La Nacion.
Piñon, A., & Gambara, H. (2005). A meta-analytic review of framming effect: Risky, attribute and goal framing [Publisher: Colegio Oﬁcial de Psicólogos del Principado de Asturias]. Psicothema, 17(2), 325–331.
Puto, C. P. (1987). The Framing of Buying Decisions*. Journal of Consumer Research, 14(3), 301–315. https://doi.org/10.1086/209115
Reiter, P. L., McRee, A.-L., Pepper, J. K., & Brewer, N. T. (2012). Default policies and parents’ consent for school-located HPV vaccination. Journal of Behavioral Medicine, 35(6), 651–657. https:// doi.org/10.1007/s10865-012-9397-1
Rothman, A. J., & Salovey, P. (1997). Shaping perceptions to motivate healthy behavior: The role of message framing [Place: US Publisher: American Psychological Association]. Psychological Bulletin, 121, 3–19. https://doi.org/10.1037/ 0033-2909.121.1.3
Schmidt, A. T., & Engelen, B. (2020). The ethics of nudging: An overview. Philosophy Compass, 15(4), e12658. https://doi.org/10.1111/phc3. 12658
Shaﬁr, E., Simonson, I., & Tversky, A. (1993). Reasonbased choice. Cognition, 49(1), 11–36. https : //doi.org/10.1016/0010-0277(93)90034-S
Shealy, T., & Klotz, L. (2015). Well-Endowed Rating Systems: How Modiﬁed Defaults Can Lead to More Sustainable Performance [Publisher: American Society of Civil Engineers]. Journal of Construction Engineering and Management, 141(10), 04015031. https://doi.org/10.1061/ (ASCE)CO.1943-7862.0001009
Szaszi, B., Palinkas, A., Palﬁ, B., Szollosi, A., & Aczel, B. (2018). A systematic scoping review of the choice architecture movement: Toward understanding when and why nudges work. Journal of Behavioral Decision Making, 31(3), 355–366.
Trujillo, C. (2013). Uruguay: New Law Renders all Citizens Organ Donors.
Tversky, A., & Kahneman, D. (1981). The Framing of Decisions and the Psychology of Choice [Publisher: American Association for the Advancement of Science]. Science, 211(4481), 453–458. https://doi.org/10.1126/science.7455683
van Dalen, H. P., & Henkens, K. (2014). Comparing the effects of defaults in organ donation systems. Social Science & Medicine, 106, 137–142. https: //doi.org/10.1016/j.socscimed.2014.01.052
Weber, E. U., & Johnson, E. J. (2009). Mindful Judgment and Decision Making. Annual Review of

Psychology, 60(1), 53–85. https://doi.org/10. 1146/annurev.psych.60.110707.163633 Wedell, D. H. (1997). Another look at reasons for choosing and rejecting. Memory & Cognition, 25(6), 873–887. https : / / doi . org / 10 . 3758 / BF03211332 Zhen, S., & Yu, R. (2016). All framing effects are not created equal: Low convergent validity between two classic measurements of framing [Number:

1 Publisher: Nature Publishing Group]. Scientiﬁc Reports, 6(1), 30071. https://doi.org/10. 1038/srep30071 Zúñiga-Fajuri, A. (2015). Increasing organ donation by presumed consent and allocation priority: Chile [Publisher: World Health Organization]. Bulletin of the World Health Organization, 93, 199– 202. https://doi.org/10.2471/BLT.14.139535

Default effect replications and extensions: Supplementary

Contents

## Disclosures

2 Data collection .................................................................................................................................... 2 Conditions reporting ........................................................................................................................... 2 Variables reporting ............................................................................................................................. 2 Author bios ......................................................................................................................................... 3 Corresponding author ......................................................................................................................... 3 Declaration of Conflict of Interest: ..................................................................................................... 3 Financial disclosure/funding:.............................................................................................................. 3 Authorship declaration:....................................................................................................................... 4 Exclusion criteria for the two replication studies................................................................................ 5
Project Process Outline ........................................................................................................................... 6 Verification of Analyses ..................................................................................................................... 6
Power analyses........................................................................................................................................ 7 Power sensitivity analyses .................................................................................................................... 11 Sample comparison between the original studies and our two studies ................................................. 12 Materials and scales related to replication part ..................................................................................... 13
Type of study .................................................................................................................................... 13 Experimental design of the original articles ..................................................................................... 13 Materials and scales related to the extensions ...................................................................................... 17 Original articles’ results ........................................................................................................................ 21 The results of Study 1 of Johnson & Goldstein (2003)..................................................................... 21 The results of Study 2 of Johnson, Bellman & Lohse, 2002 ............................................................ 21 Additional Results of Replication ......................................................................................................... 22 Additional Results of Extension hypotheses.........................................................................................29 Framework for evaluation of the replications ....................................................................................... 30 References............................................................................................................................................. 32 Appendix A...........................................................................................................................................33



Data collection Data collection was completed before analyzing the data. Conditions reporting We report all the conditions we collected. Variables reporting All variables collected for this study are reported and included in the provided data.

Author bios Subramanya Prasad Chandrashekar is a research assistant professor with the Lee Shau Kee School of Business and Administration at the Open University of Hong Kong. His research focuses on social status, lay-beliefs, and judgment and decision-making.
Paul Henne is an Assistant Professor of Philosophy at Lake Forest College. He is affiliated with the neuroscience program at Lake Forest College. He works on experimental philosophy.
Nadia Adelina, Shiyuan Zeng, Yan Ying Esther Chiu, and Yat Sum Leung were students at the University of Hong Kong during the academic year 2019-2020.
Boley Cheng was a teaching assistant at the University of Hong Kong psychology department during the academic year 2019-2020.
Gilad Feldman is an assistant professor with the University of Hong Kong psychology department. His research focuses on judgment and decision-making.
Corresponding author Gilad Feldman, Department of Psychology, University of Hong Kong, Hong Kong SAR; gfeldman@hku.hk
Declaration of Conflict of Interest: The author(s) declared no potential conflicts of interest with respect to the authorship and/or publication of this article.

## Financial disclosure/funding

Subramanya Prasad Chandrashekar would like to thank the Institute of International Business and Governance (IIBG), established with the substantial support of a grant from the Research Grants Council of the Hong Kong Special Administrative Region, China (UGC/IDS 16/17), for its support.

Authorship declaration: Table S0. Authors’ contribution

In the Table below, we employ CRediT (Contributor Roles Taxonomy) to identify the contribution and roles played by the contributors in the current replication effort. Please refer to the URL (https://www.casrai.org/credit.html ) on details and definitions of each of the roles listed below.

Role Conceptualization Pre-registration Data curation Formal analysis Funding acquisition Investigation Methodology Pre-registration peer review / verification Data analysis peer review/verification Project administration Resources Software Supervision Validation Visualization Writing-original draft Writing-review and editing

Gilad Feldman
X X X
X X X X
X X
X
X

Exclusion criteria for the two replication studies
1. Subjects indicating a low proficiency of English (self-report < 5, on a 1-7 scale); 2. Subjects who self-report not being serious about filling in the survey (self-report <
4, on a 1-5 scale); 3. Subjects who correctly guessed the hypothesis of this study in the funnelling
section; 4. Have seen or done the survey before; 5. Subjects who failed to complete the survey. (duration = 0, leave question blank); 6. Not from the United States;

Project Process Outline

The current replication is part of the mass pre-registered replication project, with the primary aim of revisiting well-known research findings in the area of judgment and decision making (JDM) and examining the reproducibility and replicability of these findings. The current replication study followed the same project outline as noted below. For each of the replication projects, researchers completed full pre-registrations, data analysis, and APA style submission-ready reports. The authors independently reproduced the materials and designed the replication experiment, with a separate pre-registration document. The researchers then peer-reviewed one another to try and arrive at the best possible design. Then, the lead and corresponding authors reviewed the integrated work and the last corresponding author made final adjustments and conducted the pre-registration and data collection. The OSF page of the project contains the Qualtrics survey design used for data collection with pre-registration documents submitted by each of the researchers. In the manuscript, we followed the most conservative of the pre-registrations.
Figure S1. Project process diagram

Verification of Analyses
Initial analyses were conducted by the independent researchers, who used JAMOVI (jamovi project, 2018) or R for data analyses. In preparing this manuscript, the lead and corresponding authors verified the analyses in R.

Power analyses
The rationale for reconstructing the original dataset and re-running logistic regression: authors of the original studies did not report full statistical results necessary for calculating effect size and power analysis. Hence, we had to re-conduct the test based on the data (consent rates/participation rates in different experimental conditions) available in the original paper. Given the study, designs involved binary outcome variables frequency tables and figures noted in the original papers allowed us to reconstruct accurate data collected during the original studies.
We note consistencies related to the power analysis details reported as part of the preregistrations across Group A and Group B (OSF: Group A - https://osf.io/mhwbe/, Group B https://osf.io/j4rpc/.). Below we report a rectified power analysis based on the original study’s results. Please refer to Appendix A of the current supplementary document for explanations of the differences across Group’s (A & B) analysis and the power analysis steps reported below.

Steps for power analysis (Johnson & Goldstein, 2003): 1. Conducted Binomial Logistic Regression in Jamovi based on the reconstructed data file (“OrigOrganDonation.csv” available on the OSF page of the project). 2. We calculated the Odds Ratios of the Binomial Logistic Regression results in Jamovi. 3. Used the odds ratio for the power analysis with GPower (Faul et al., 2007).

## Supplementary

screenshots

Generating Odds ratios of the Binomial Logistic Regression results in Jamovi

Power analysis done by GPower 3.1 -- default effect (Opt-out vs. Opt-in) in Johnson & Goldstein, 2003

Steps for power analysis (Johnson, Bellman & Lohse, 2002): 1. Conducted a Binomial Logistic Regression analysis in Jamovi based on the reconstructed data file (“OrigHealthSurvey.csv” available on the OSF page of the project). 2. Used the odds ratio from Jamovi output for the power analysis with GPower.



Odds ratio Pr(Y=1|X=1) H0 α err prob Power (1-β err prob) R² other X X distribution X parm μ X parm σ Critical z Total sample size Actual power

= 4.3137 = 0.5 = 0.05 = 0.95 =0 = Normal =0 =1 = 1.9599640 = 44 = 0.9545112

Power analysis by GPower 3.1 -default effect (No-default vs. opt-in) in Johnson, Bellman & Lohse, 2002

Power analysis by GPower 3.1-framing effect (positive vs. negative) in Johnson, Bellman & Lohse, 2002

Notes: We choose a sufficiently larger sample size to ensure sufficient power of 95% to detect effects noted in the target studies and the effects of the proposed extension hypothesis that included six between-subjects conditions (conceptual replication of Johnson et al., 2002).
Power sensitivity analyses

Post-hoc power sensitivity analysis based on our intended goal of combined sample size of 2000 participants indicate that the final sample has 96.93% power (at α = .05) detect an small-medium effect size (Odds Ratio = 1.50).

Sample comparison between the original studies and our two studies
Table S2. Sample differences and similarities between the original studies and our replication samples

Differences and similarities between participant sample in the original study and replication.

Note: (*) 480 out of 954 participants in the Mturk sample were assigned to conditions that aimed to replicate the original findings. The remaining 474 participants were assigned to experimental conditions designed as part of the extension.

Materials and scales related to replication part
Type of study
Johnson & Goldstein, 2003: Between subjects design Johnson, Bellman & Lohse, 2002: Experimental Manipulations (Mixed design).
Experimental design of the original articles
Participants were asked to imagine that they have just moved to a new state and that they are filling out paperwork related to their move. The instruction that noted that they are "filling out the required online registration forms" upon their arrival at the new state, which was not present in Johnson & Goldstein (2003). This addition aimed to make the transition from the organ donor form (Part 1) to the health survey (Part 2) related forms more coherent.
Johnson & Goldstein, 2003 Three studies were reported in Johnson and Goldstein’s (2003) work to evaluate the
effect of the default on the agreement rate of organ donations. The focus of the current replication study is on the first experiment, which investigates the effect of three default conditions (i.e. opt-out, opt-in and no-default condition) on organ donation rate through the format of an online survey. Experiment 1 from the original research used a 3 (default options) between-subject design. The respondents of an online experiment were assigned to one of the three conditions with different default options. Participants were asked whether they would be donors based on one of the three questions with varying defaults. Table 7 shows the three experimental conditions.

Table S3. Experimental Design of Johnson & Goldstein, 2003 and our replication studies

Default Effect (Johnson & Goldstein, 2003) Participants were told to complete an online survey, in the survey, they were told to assume that they have just moved to a new state and were asked whether they would be donors based on one of the three questions with varying defaults. Participants were randomly assigned to answer 1 out of 3 different default conditions of the question.

Independent Variable: Default (between subjects)

IV condition 1: Opt-out condition
Participants answered the following multiplechoice question:

IV condition 2: Opt-in condition
Participants answered the following multiplechoice question:

IV condition 3: No-default (no default) condition Participants answered the following multiplechoice question:

donor. Please choose organ donor. Please donor status.

The option “YES Organ donor” was set as the default option.

The option “NO - Not No options were set as organ donor” was set as the default option. the default option.

Dependent Variable: Scoring the DV:

Donation agreement rate

Two choices were given in the multiple-choice questions, which were coded with numerical values for further calculation:
● YES - Organ donor = 1 ● NO - Not organ donor = 0 Value ‘1’ indicated consent for organ donation, whereas, ‘0’ indicated disagreeing to donate the organs.

Johnson, Bellman & Lohse, 2002

## Experiment

2 of Johnson, Bellman & Lohse, 2002 employed a 2(framing) x 3(default) between-subject design, wherein each respondent of an online health survey was randomly assigned to answer one of six variations of the same question at the end of the survey they just completed. The dependent variable essentially asked whether the respondent would like to be contacted in the future for opportunities to participate in more health surveys. Table 1 details the six experimental conditions.
Table S4. . Experimental Design of Experiment 2 in Johnson, Bellman & Lohse, 2002 and our replication studies
Default and Framing Effect (Experiment 2 in Johnson, Bellman & Lohse, 2002) Participants first completed a health survey online and then were told to answer a question that evaluates the effect of framing and default on participant’s preferences on whether or not to receive notification for more information about health survey.

Participants were randomly assigned to 1 out of 6 different default and framing conditions and were required to confirm their choices accordingly. Experimental conditions varied in the structure of the question, i.e., the structure of the question (the DV) presented to the participants at the end of the health survey varied on framing and defaults.

Notify me about more health surveys.

IV condition 3: No default condition No default option was given.

Dependent Variable DV item variations in framing:

DV item variations in default:

Participants were required to choose whether or not to receive notification about more health surveys.

Participants were required to choose whether or not to receive notification about more health surveys.

different for the two IV conditions.

different for the three IV conditions.

Positive framing condition ): ● Yes = 1 ● No = 0

Opt-out condition : ● Yes = 1 ● No = 0

Negative framing condition : ● Yes = 0 ● No = 1

Opt-in condition : ● Yes = 0 ● No = 1

The across both framing conditions the response to the DV was scored as “1” when the response meant participants agreed to receive more information about health survey, and the value of “0” meant declining such an offer.

No default condition : ● Yes = 1 ● No = 0
The across three defaults conditions the response to the DV was scored as “1” when the response meant participants agreed to receive more information about health survey, and the value of “0” meant declining such an offer.

Materials and scales related to the extensions

Table S5. Experimental design of Extension 1: Organ donation scenario (Permanent vs.

Temporary)

IV1: Choice permanence (permanent vs. temporary)
● Between-subjects ● This is an extension IV2: Default Options (opt-in, opt-out vs no-default)
● between-subjects

IV1: Permanent
Refer to the scenarios of the originals study noted above.

IV1: Temporary
Scenarios in the temporary mirrored that of the original study except for one additional information: The participant is told that organ donation status is renewable and can be changed every 3 years.
“Please note that you will need to renew your option every 3 years.”

IV2: Opt-in

Dependent Variable

Participants need to choose whether they want to confirm or change the status of NOT to be an organ donor
IV2: Opt-out
Participants need to choose whether they want to confirm or change the

DV title: participation
Specific DV item: participant’s participation to become or not become an organ donor (“want to be an organ donor” vs “do not want to be an organ donor”)
● Organ donor: if participant selects either one of the following options. ○ “CONFIRM - I want to be an organ donor.” ○ “CHANGE - I want to be an organ donor.”
● Not organ donor: if participant selects either one of the following options. ○ “CONFIRM - I do not want to be an organ donor.”

status of To be an organ donor

○ “CHANGE - I do not want to be an organ donor.”

IV2: No-default
Participants were merely required to choose with No prior default and they can decide whether to be an organ donor or not.
Note: The extension was part of the Sample 1 data collection

Extension 2: Conceptual replication of Johnson et al. (2002). Extension 2 mirrored the Experiment 2 of Johnson, Bellman & Lohse, 2002 : a
2(framing) x 3(default) between-subject design, wherein each respondent answer one of six variations of the same questions. The dependent variable essentially asked whether the respondent would like to receive further information on organ donation.
Table S6. Experimental design of Extension 2

Extension 2: Default and Framing Effect:
They were manipulated by changing the format of the statement with default and framing conditions. Participants were randomly assigned to 1 out of 6 different versions of the statements, and were required to confirm their choices accordingly.

2. Framing condition: Positive framing
- The following statement was randomly assigned to the participants : “Send me more information about organ donation”

2. Framing condition: Positive framing
- The following statement was randomly assigned to the participants : “Send me more information about organ donation”

2. Framing condition: Positive framing
- The following statement was randomly assigned to the participants : “Send me more information about organ donation”

Dependent Variable:
Participation rate

Participants would indicate their preference of receiving notifications for additional organ donation information under different default and framing conditions, and the effects of default and framing would be reflected by the participation rate.
Opt-out condition (IV1):

We reproduced the results of the original study to help us accurately pin-point the effect sizes for the current replication and to ascertain the degree of reproducibility.
The results of Study 1 of Johnson & Goldstein (2003)
Table S7. The results of Binomial Logistic Regression

The results of Study 2 of Johnson, Bellman & Lohse, 2002
Table S8. The results of Binomial Logistic Regression

Predictor
Intercept
Framing: Positive vs. Negative
Default Condition: No-default vs. Opt-in Opt-out – Opt-in
Framing ✻ Default Condition: (Positive vs. Negative ) ✻ (Nodefault vs. Opt-in) (Positive vs. Negative ) ✻ (Optout vs. Opt-in)

Table S9. Descriptive table of the participation rates.

Replication Study
Replication of Experiment 1 from Johnson & Goldstein (2003)
Replication of Experiment 2 from Johnson, Bellman & Lohse (2002)
Note. N = 1920;

Experimental Conditions

Opt-in default Opt-out default

No-default (no default)

Opt-in default Opt-out default No-default (no default)

Positive Framing Negative Framing Positive Framing Negative Framing Positive Framing Negative Framing

Positive Framing Negative Framing Positive Framing Negative Framing Positive Framing Negative Framing

Summary of the replication results: Logistic regression analysis conducted separately for Sample 1 and Sample 2

Intercept Default: No-default – Opt-in Default: Opt-out – Opt-in Intercept Default: No-default – Opt-in Default: Opt-out – Opt-in Framing: Positive – Negative Framing ✻ Defaults:
(Positive – Negative) ✻ (No-default–Opt-in) (Positive – Negative) ✻ (Opt-out –Opt-in)

Note. Estimates represent the odds of dependent variable = “1” vs. “0”; N (Sample 1)= 480; N (Sample 2) = 966;

Odds ratio with 95% C.I.
1.44 [1.05, 1.98] 1.43 [0.91, 2.26] 1.73 [1.09, 2.77] 0.44 [0.31, 0.61] 0.82 [0.50, 1.34] 0.67 [0.41, 1.10] 12.34 [7.17, 21.24]
2.30 [0.98, 5.39] 2.21 [0.98, 5.03]
1.79 [1.43, 2.26] 1.36 [0.98, 1.90] 1.64 [1.17, 2.30] 0.58 [0.42, 0.80] 0.55 [0.34, 0.89] 0.83 [0.52, 1.31] 21.74 [11.15, 42.42]
3.21 [1.10, 9.39] 3.70 [1.07, 12.81]

Notes on Johnson & Goldstein (2003) replication: In sample 1, participants in the No-Default condition were not more likely to consent to organ donation (67.3%) than
participants the Opt-In condition (59.0%) (b = 0.36, p = .124, OR = 1.43, 95% CI [0.91, 2.26]). In sample 2, participants in the NoDefault condition were more likely to consent to organ donation (70.9%) than participants the Opt-In condition (64.2%) (b = 0.31, p = .068, OR = 1.36, 95% CI [0.98, 1.90]).

Notes on Johnson et al. (2002) replication: In sample 1, participants in the No-Default did not consent to receive health-related information (59.0%) at a higher rate than
participants the Opt-In condition (57.3%) (b = -0.20, p = .433, OR = 0.82, 95% CI [0.50, 1.34]). In sample 2, participants in the NoDefault condition consented to receive health related information (60.6%) at a lower rate than participants the Opt-In condition (64.8%) (b = -0.60, p = .015, OR = 0.55, 95% CI [0.34, 0.89]).

Table S13. Summary of the Johnson et al.’s (2002) replication results: Logistic regression analysis conducted separately for each frame

Target By Positive Frame
Part 1 (Johnson & Goldstein, 2003)
By Negative Frame
Part 1 (Johnson & Goldstein, 2003)

Predictor
Intercept Default: No-default – Opt-in Default: Opt-out – Opt-in
Intercept Default: No-default – Opt-in Default: Opt-out – Opt-in

8.40 [3.98, 17.74] 1.85 [1.05, 3.24] 1.79 [1.03, 3.11]
0.51 [0.40, 2.26] 0.67 [0.47, 0.94] 0.75 [0.54, 1.05]

Additional Results of Extension hypotheses

Table S14. Descriptive table for extension hypotheses.

Extensions Mturk Sample 1: Organ donor study in the temporary organ-donor condition.
Mturk Sample 2: Organ donor scenario adopted with both framing and default effects.
Note. Sample 1 (N) = 954; Sample 2 (N) = 966;

Table S15. Criteria for evaluation of replications by LeBel et al. (2018). A classification of relative methodological similarity of a replication study to an original study. “Same” (“different”) indicates the design facet in question is the same (different) compared to an original study. IV = independent variable. DV = dependent variable. “Everything controllable” indicates design facets over which a researcher has control. Procedural details involve minor experimental particulars (e.g., task instruction wording, font, font size, etc.).

Figure S2. Criteria for evaluation of replications by LeBel et al. (2019). A taxonomy for comparing replication effects to target article original findings.

Note: LeBel et al. (2019) suggested a replication evaluation using three factors: (a) whether a signal was detected (i.e., the confidence interval for the replication Effect size (ES) excludes one), (b) consistency of the replication ES with the original study's ES, and (c) precision of the replication's ES estimate (see Figure S# in the supplementary material).



Fual, F., Erdfelder, E., Lang, A., & Buchner, A. (2007). G*Power: A flexible statistical power analysis program for the social, behavioral, and biomedical sciences. Behavior Research Methods, 39(2), 175–191. https://doi.org/10.3758/BF03193146
The jamovi project (2020). jamovi (Version 1.2) [Computer Software]. Retrieved from https://www.jamovi.org
Johnson, E. J., Bellman, S., & Lohse, G. L. (2002). Defaults, framing and privacy: Why opting in-opting out. Marketing Letters, 13(1), 5-15.
Johnson, E. J., & Goldstein, D. (2003). Do defaults save lives? Science, 302, 1338–1339.

## Appendix A

Explanation of the power analysis reported as part of the Pre-registration across Group A and Group B.

Please note that the power analysis conducted based on the original studies is reported in Group A and Group B’s supplementary material documents submitted as part of the preregistration. (see OSF links: Group A = https://osf.io/5e3r8 ; Group B =
https://osf.io/3kdqb)

Why are there some differences between the pre-registration reported as part of the supplementary from the ones of Pre-registration of Group A & B?
Essentially results change a little based on the reference level specified as part of the data analysis. In our supplementary document, we report results based on the default effect’s reference level = Opt-in, as this reference level allows for easy evaluations of the arguments and results reported in the original studies. It does not affect us in a big way because our final sample size is much bigger than any of the power analyses conducted based on different combinations of reference levels.
Power analysis of Johnson & Goldstein, 2003:
The power analysis reported as part of the supplementary material is very similar to the one preregistrations across Group A and Group B. The numbers differ across these documents because of the variations in the reference levels specified as part of data analysis using JAMOVI (it’s the same in R).
Power analysis related to effect size reported in supplymentary document:
We reproduce the results reported as part of the supplementary document. Reference level set were: (DV= 0; default condition = Optin)

Power analysis related to effect size reported in Group A Pre-registration document: (https://osf.io/5e3r8; Page 16)
We reproduce the results reported as part of Group A’s pre-registration document. Reference level set were: (DV= 0; default condition = OptOut)

Power analysis related to effect size reported in Group B Pre-registration document: (https://osf.io/3kdqb ; Page 27)
We reproduce the results reported as part of Group B’s pre-registration document. Reference level set were: (DV= 0; default condition = Optin). The analysis and results of Group B are the same as the supplementary material (because the reference levels were the same).

Power analysis of Johnson et al. 2002:
Power analysis reported as part of the supplementary material is very similar to the one preregistrations across Group A and Group B. The numbers differ across these documents because of the variations in the reference levels specified as part of data analysis using JAMOVI (or in R).
Power analysis related to effect size reported in supplementary document:
We reproduce the results reported as part of the supplementary document. Reference level set were: (DV= 0; default condition = Optin, Framing = negative)

Power analysis reported in Group A Pre-registration document: (https://osf.io/5e3r8 ; Page 18/19)
We reproduce the results reported as part of Group A’s pre-registration document. Reference level set were: (DV= 0; default condition = OptOut; Framing = positive)

Power analysis related to effect size reported in Group B Pre-registration document: (https://osf.io/3kdqb; Page 19)
We reproduce the results reported as part of Group B’s pre-registration document. The reference level set were: (DV= 0; default condition = Opt-out; Framing = positive). Please note the group B reconstructed the data of the original study and used different labels (data is identical) as presented below (Reference level guide: Opt-out = subscribed; Neutral = No default; Opt-in = unsubscribed).


## Figures

*Figure 1. Results of direct replications of Johnson and Goldstein (2003).*

*Figure 2. Results of direct replication of Johnson et al.*

*Figure 3. Results of Extension 1. Percentage of participants who consented to organ donation between permanent vs.*

*Figure 4. Extension 2: Percentage of participants who agreed to be notiﬁed about further information about organ donation in the future.*

*Figure 5. Effect sizes in Johnson and Goldstein (2003), Johnson et al. (2002), and the current replication. Estimates and conﬁdence intervals are plotted on a natural logarithmic scale.*


## Tables (unlocated in body)

### Table 1
*Study stimuli for the direct replication of Johnson and Goldstein (2003) [Introduction for participants in Opt-Out/Opt-in Conditions]: Imagine that you have just moved to a new state and are currently ﬁlling out the required online registration forms when you are asked to indicate your organ donor s…*

<table>
  <thead>
    <tr>
      <th></th>
      <th>5</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Table 1</td>
      <td>Opt-Out conditions, the ‘yes’ response was pre-selected.<br>In positively framed Opt-In conditions, the ‘No’ response</td>
    </tr>
    <tr>
      <td>Study stimuli for the direct replication of Johnson and</td>
      <td>was pre-selected. In negatively framed Opt-Out condi-</td>
    </tr>
    <tr>
      <td>Goldstein (2003)</td>
      <td>tions, the ‘No’ response was pre-selected. In negatively</td>
    </tr>
    <tr>
      <td>[Introduction for participants in Opt-Out/Opt-in</td>
      <td>framed Opt-in conditions, the ‘yes’ response was pre-</td>
    </tr>
    <tr>
      <td>Conditions]:</td>
      <td>selected.</td>
    </tr>
    <tr>
      <td>Imagine that you have just moved to a new state and</td>
      <td>Extensions</td>
    </tr>
    <tr>
      <td>are currently ﬁlling out the required online registration</td>
      <td></td>
    </tr>
    <tr>
      <td>forms when you are asked to indicate your organ donor</td>
      <td>Extension 1: The effect of choice permanence.</td>
    </tr>
    <tr>
      <td>status. The default in this state is that you ARE automat-ically enrolled to be an organ donor. You are given the</td>
      <td>Participants in Sample 1 were part of the choice-<br>permanence extension. As such, participants in Sam-</td>
    </tr>
    <tr>
      <td>choice of whether to conﬁrm or to change this status.</td>
      <td>ple 1 were randomly assigned to one of two between-</td>
    </tr>
    <tr>
      <td>Please select an option</td>
      <td>participants conditions (temporary or permanent). Par-<br>ticipants assigned to the temporary conditions took the</td>
    </tr>
    <tr>
      <td>[Opt-out]:</td>
      <td>same survey as those in the permanent conditions—only</td>
    </tr>
    <tr>
      <td>Assume you moved to a new state in which the default</td>
      <td>they received the following additional instruction at the</td>
    </tr>
    <tr>
      <td>is that you are an organ donor, you are therefore by</td>
      <td>beginning of part 1 of the study:</td>
    </tr>
    <tr>
      <td>default enrolled as an organ donor. Please choose your</td>
      <td>“Please note: Your organ donor authorization, if</td>
    </tr>
    <tr>
      <td>preferred organ donor status:</td>
      <td>granted, would be for 3 years only, meaning that after<br>3 years you will be asked to reconﬁrm your organ donor</td>
    </tr>
    <tr>
      <td>Yes-I want to be an organ donor</td>
      <td>decision.”</td>
    </tr>
    <tr>
      <td>No- I do not want to be an organ donor</td>
      <td>Participants in the permanent conditions had no ad-<br>ditional instructions.</td>
    </tr>
    <tr>
      <td>[Opt-in]:</td>
      <td>Extension 2: Conceptual replication of Experimental 2</td>
    </tr>
    <tr>
      <td>Assume you moved to a new state in which the default</td>
      <td>of Johnson et al. (2002).</td>
    </tr>
    <tr>
      <td>is that you are not an organ donor, you are therefore by</td>
      <td>All the participants in Sample 2 took part in a differ-</td>
    </tr>
    <tr>
      <td>default not enrolled as an organ donor. Please choose</td>
      <td>ent extension. Immediately after completing Part 1 of</td>
    </tr>
    <tr>
      <td>your preferred organ donor status:</td>
      <td>the study but just before Part 2, participants read the<br>following instructions (see Table 3 for details):</td>
    </tr>
    <tr>
      <td>Yes-I want to be an organ donor</td>
      <td>“Would you like to receive further information about</td>
    </tr>
    <tr>
      <td>No- I do not want to be an organ donor</td>
      <td>organ donation through MTurk? If you indicate your<br>approval, we’ll contact you through MTurk using your</td>
    </tr>
    <tr>
      <td>[No-default]:</td>
      <td>worker ID with further information about organ dona-</td>
    </tr>
    <tr>
      <td>Assume you moved to a new state, therefore, you need</td>
      <td></td>
    </tr>
    <tr>
      <td></td>
      <td>tion.”</td>
    </tr>
    <tr>
      <td>to select enrollment as an organ donor. Please choose</td>
      <td>These participants were randomly assigned to 1 of 6</td>
    </tr>
    <tr>
      <td>your preferred organ donor status:</td>
      <td>conditions in a 2 (framing: Positive vs. Negative) times<br>3 (default option: Opt-Out vs. Opt-In vs. No-Default)</td>
    </tr>
    <tr>
      <td>Yes-I want to be an organ donor</td>
      <td>between-participants design (for details, see Table S6 in</td>
    </tr>
    <tr>
      <td>No- I do not want to be an organ donor</td>
      <td>the supplementary section). After reading the above in-<br>struction, participants selected “Yes” or “No” to a ques-<br>tion asking for consent to receiving further information<br>on organ donation. Each of the default conditions in-</td>
    </tr>
    <tr>
      <td>Participants then answered four generic questions on</td>
      <td>volved either a positive (“Send me more information</td>
    </tr>
    <tr>
      <td>their health in general (for details, see Table S4 supple-mentary section). Participants then read:</td>
      <td>about organ donation”) or negative (“Do NOT send me<br>more information about organ donation”) framing. The</td>
    </tr>
    <tr>
      <td>“You are almost at the end of the survey. Thank you</td>
      <td>responses were pre-selected in the Opt-In and Opt-Out</td>
    </tr>
    <tr>
      <td>for taking part. Would you be interested in being notiﬁed</td>
      <td>default conditions mirroring the experimental design of</td>
    </tr>
    <tr>
      <td>about other policy/health-related surveys? (If yes, we will</td>
      <td>Experiment 2 of Johnson et al. (2002). In positively</td>
    </tr>
    <tr>
      <td>contact you through MTurk using your MTurk worker ID)”</td>
      <td>framed Opt-Out conditions, the ‘yes’ response was pre-</td>
    </tr>
    <tr>
      <td>Participants answered by selecting “Yes” or “No.”</td>
      <td>selected. In positively framed Opt-In conditions, the</td>
    </tr>
    <tr>
      <td>Each condition had a positive (“Notify me about more</td>
      <td>‘No’ response was pre-selected. In negatively framed</td>
    </tr>
    <tr>
      <td>health surveys.”) or negative (“Do NOT notify me about</td>
      <td>Opt-Out conditions, the ‘no’ response was pre-selected.</td>
    </tr>
    <tr>
      <td>more health surveys.”) framing. In positively framed</td>
      <td></td>
    </tr>
  </tbody>
</table>

### Table 4
*Classiﬁcation of replications based on LeBel et al.*

<table>
  <thead>
    <tr>
      <th></th>
      <th>7</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Table 3</td>
      <td>Table 4</td>
    </tr>
    <tr>
      <td>Study stimuli for the on conceptual replication of Johnson</td>
      <td>Table 4. Classiﬁcation of replications based on LeBel et al.</td>
    </tr>
    <tr>
      <td>et al. (2002)</td>
      <td>(2019)<br>Design facet Replication study</td>
    </tr>
    <tr>
      <td>[Introduction]:</td>
      <td>IV operationalization Same</td>
    </tr>
    <tr>
      <td>Typically, regardless of your organ donor decision, the</td>
      <td>DV operationalization Same</td>
    </tr>
    <tr>
      <td>state online systems ask you to answer a number of</td>
      <td>IV stimuli Same</td>
    </tr>
    <tr>
      <td>health questions. Please answer the following. All the</td>
      <td>DV stimuli Same</td>
    </tr>
    <tr>
      <td>data will be kept completely conﬁdential.</td>
      <td>Procedural details Similar<br>Physical settings Different</td>
    </tr>
    <tr>
      <td>You are almost at the end of the survey. Thank you</td>
      <td>Contextual variables Different</td>
    </tr>
    <tr>
      <td>for taking part. Would you be interested in being noti-ﬁed about other policy/health-related surveys? (If yes,</td>
      <td>Replication classiﬁcation Very close replication</td>
    </tr>
    <tr>
      <td>we will contact you through MTurk using your MTurk</td>
      <td></td>
    </tr>
    <tr>
      <td>worker ID)</td>
      <td>Part 1: Replication of Johnson and Goldstein (2003)</td>
    </tr>
    <tr>
      <td>[Positive frame, Opt-out]:</td>
      <td></td>
    </tr>
    <tr>
      <td>Send me more information about organ donation.</td>
      <td>Consistent with the original study, participants in<br>the Opt-Out condition consented to organ donation at</td>
    </tr>
  </tbody>
</table>

### Table 10
*Summary of the ﬁndings of Johnson et al. (2002) across original, direct replication, and conceptual replication studies Predictor Default condition: No-Default– Opt-In Opt-Out – Opt-In Framing condition: Positive – Negative Original study’s ﬁndings Signal Directionality Yes Consistent Yes Consistent…*

<table>
  <thead>
    <tr>
      <th>Table 7</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Summary of the replication results of Part 1 (Johnson Goldstein, 2003) based on logistic regression analysis</td>
      <td></td>
      <td></td>
      <td>Model 1</td>
      <td></td>
      <td></td>
      <td></td>
      <td>Model 2</td>
      <td></td>
    </tr>
    <tr>
      <td>Predictor</td>
      <td>Estimate</td>
      <td>Z</td>
      <td>p</td>
      <td>OR [95% CI]</td>
      <td>Estimate</td>
      <td>Z</td>
      <td>p</td>
      <td>OR [95% CI]</td>
    </tr>
    <tr>
      <td>Intercept</td>
      <td>-0.84 (0.11)</td>
      <td>-7.65</td>
      <td>&lt;.001</td>
      <td>0.43 [0.35, 0.53]</td>
      <td>-0.68 (0.12)</td>
      <td>-5.78</td>
      <td>&lt;.001</td>
      <td>0.51 [0.40, 0.64]</td>
    </tr>
    <tr>
      <td>Framing: Positive – Negative</td>
      <td>3.31 (0.14)</td>
      <td>24.14</td>
      <td>&lt;.001</td>
      <td>27.27 [20.97, 35.88]</td>
      <td>2.73 (0.21)</td>
      <td>12.96</td>
      <td>&lt;.001</td>
      <td>15.30 [10.23, 23.40]</td>
    </tr>
    <tr>
      <td>Default: No-Default – Opt-In</td>
      <td>-0.12 (0.15)</td>
      <td>-0.81</td>
      <td>.417</td>
      <td>0.89 [0.66, 1.19]</td>
      <td>-0.40 (0.18)</td>
      <td>-2.29</td>
      <td>.021</td>
      <td>0.66 [0.47, 0.94]</td>
    </tr>
    <tr>
      <td>Default: Opt-Out – Opt-In</td>
      <td>-0.05 (0.15)</td>
      <td>-0.35</td>
      <td>.724</td>
      <td>0.95 [0.71, 1.27]</td>
      <td>-0.29 (0.17)</td>
      <td>-1.66</td>
      <td>.096</td>
      <td>0.75 [0.54, 1.05]</td>
    </tr>
    <tr><td colspan="9"><strong>Interaction term:</strong></td></tr>
    <tr>
      <td>(Positive – Negative) × (No-Default–Opt-In)</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>1.00 (0.33)</td>
      <td>3.02</td>
      <td>.003</td>
      <td>2.74 [1.43, 5.35]</td>
    </tr>
    <tr>
      <td>(Positive – Negative) × (Opt-Out –Opt-In)</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>0.85 (0.33)</td>
      <td>2.57</td>
      <td>.010</td>
      <td>2.33 [1.23, 4.49]</td>
    </tr>
    <tr><td colspan="9"><strong>Note. Estimates represent the odds of the dependent variable = “1” vs. “0”. Standard errors are reported within the brackets.</strong></td></tr>
  </tbody>
</table>

<table>
  <thead>
    <tr>
      <th>Table 7</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Summary of the replication results of Part 1 (Johnson Goldstein, 2003) based on logistic regression analysis</td>
      <td></td>
      <td></td>
      <td>Model 1</td>
      <td></td>
      <td></td>
      <td></td>
      <td>Model 2</td>
      <td></td>
    </tr>
    <tr>
      <td>Predictor</td>
      <td>Estimate</td>
      <td>Z</td>
      <td>p</td>
      <td>OR [95% CI]</td>
      <td>Estimate</td>
      <td>Z</td>
      <td>p</td>
      <td>OR [95% CI]</td>
    </tr>
    <tr>
      <td>Intercept</td>
      <td>-0.84 (0.11)</td>
      <td>-7.65</td>
      <td>&lt;.001</td>
      <td>0.43 [0.35, 0.53]</td>
      <td>-0.68 (0.12)</td>
      <td>-5.78</td>
      <td>&lt;.001</td>
      <td>0.51 [0.40, 0.64]</td>
    </tr>
    <tr>
      <td>Framing: Positive – Negative</td>
      <td>3.31 (0.14)</td>
      <td>24.14</td>
      <td>&lt;.001</td>
      <td>27.27 [20.97, 35.88]</td>
      <td>2.73 (0.21)</td>
      <td>12.96</td>
      <td>&lt;.001</td>
      <td>15.30 [10.23, 23.40]</td>
    </tr>
    <tr>
      <td>Default: No-Default – Opt-In</td>
      <td>-0.12 (0.15)</td>
      <td>-0.81</td>
      <td>.417</td>
      <td>0.89 [0.66, 1.19]</td>
      <td>-0.40 (0.18)</td>
      <td>-2.29</td>
      <td>.021</td>
      <td>0.66 [0.47, 0.94]</td>
    </tr>
    <tr>
      <td>Default: Opt-Out – Opt-In</td>
      <td>-0.05 (0.15)</td>
      <td>-0.35</td>
      <td>.724</td>
      <td>0.95 [0.71, 1.27]</td>
      <td>-0.29 (0.17)</td>
      <td>-1.66</td>
      <td>.096</td>
      <td>0.75 [0.54, 1.05]</td>
    </tr>
    <tr><td colspan="9"><strong>Interaction term:</strong></td></tr>
    <tr>
      <td>(Positive – Negative) × (No-Default–Opt-In)</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>1.00 (0.33)</td>
      <td>3.02</td>
      <td>.003</td>
      <td>2.74 [1.43, 5.35]</td>
    </tr>
    <tr>
      <td>(Positive – Negative) × (Opt-Out –Opt-In)</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>0.85 (0.33)</td>
      <td>2.57</td>
      <td>.010</td>
      <td>2.33 [1.23, 4.49]</td>
    </tr>
    <tr><td colspan="9"><strong>Note. Estimates represent the odds of the dependent variable = “1” vs. “0”. Standard errors are reported within the brackets.</strong></td></tr>
  </tbody>
</table>

### Table 8
*Summary of the replication results of Extension 2 (conceptual replication of Johnson et al. (2002) based on logistic regression analysis Predictor Intercept Framing: Positive – Negative Default: No-Default – Opt-In Default: Opt-Out – Opt-In Interaction terms: (Positive – Negative) × (No-Default–Opt-…*

<table>
  <thead>
    <tr>
      <th>Table 7</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Summary of the replication results of Part 1 (Johnson Goldstein, 2003) based on logistic regression analysis</td>
      <td></td>
      <td></td>
      <td>Model 1</td>
      <td></td>
      <td></td>
      <td></td>
      <td>Model 2</td>
      <td></td>
    </tr>
    <tr>
      <td>Predictor</td>
      <td>Estimate</td>
      <td>Z</td>
      <td>p</td>
      <td>OR [95% CI]</td>
      <td>Estimate</td>
      <td>Z</td>
      <td>p</td>
      <td>OR [95% CI]</td>
    </tr>
    <tr>
      <td>Intercept</td>
      <td>-0.84 (0.11)</td>
      <td>-7.65</td>
      <td>&lt;.001</td>
      <td>0.43 [0.35, 0.53]</td>
      <td>-0.68 (0.12)</td>
      <td>-5.78</td>
      <td>&lt;.001</td>
      <td>0.51 [0.40, 0.64]</td>
    </tr>
    <tr>
      <td>Framing: Positive – Negative</td>
      <td>3.31 (0.14)</td>
      <td>24.14</td>
      <td>&lt;.001</td>
      <td>27.27 [20.97, 35.88]</td>
      <td>2.73 (0.21)</td>
      <td>12.96</td>
      <td>&lt;.001</td>
      <td>15.30 [10.23, 23.40]</td>
    </tr>
    <tr>
      <td>Default: No-Default – Opt-In</td>
      <td>-0.12 (0.15)</td>
      <td>-0.81</td>
      <td>.417</td>
      <td>0.89 [0.66, 1.19]</td>
      <td>-0.40 (0.18)</td>
      <td>-2.29</td>
      <td>.021</td>
      <td>0.66 [0.47, 0.94]</td>
    </tr>
    <tr>
      <td>Default: Opt-Out – Opt-In</td>
      <td>-0.05 (0.15)</td>
      <td>-0.35</td>
      <td>.724</td>
      <td>0.95 [0.71, 1.27]</td>
      <td>-0.29 (0.17)</td>
      <td>-1.66</td>
      <td>.096</td>
      <td>0.75 [0.54, 1.05]</td>
    </tr>
    <tr><td colspan="9"><strong>Interaction term:</strong></td></tr>
    <tr>
      <td>(Positive – Negative) × (No-Default–Opt-In)</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>1.00 (0.33)</td>
      <td>3.02</td>
      <td>.003</td>
      <td>2.74 [1.43, 5.35]</td>
    </tr>
    <tr>
      <td>(Positive – Negative) × (Opt-Out –Opt-In)</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>0.85 (0.33)</td>
      <td>2.57</td>
      <td>.010</td>
      <td>2.33 [1.23, 4.49]</td>
    </tr>
    <tr><td colspan="9"><strong>Note. Estimates represent the odds of the dependent variable = “1” vs. “0”. Standard errors are reported within the brackets.</strong></td></tr>
  </tbody>
</table>

### Table 9
*Summary and comparison of ﬁndings of the current replication study and the target studies Part Part 1: Johnson and Goldstein (2003) * Part 2: Johnson et al. (2002) Target effect Default effects: No-Default vs. Opt-In Default effects: Opt-Out vs. Opt-In Default effects: No-Default vs.*

<table>
  <thead>
    <tr>
      <th>Table 7</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Summary of the replication results of Part 1 (Johnson Goldstein, 2003) based on logistic regression analysis</td>
      <td></td>
      <td></td>
      <td>Model 1</td>
      <td></td>
      <td></td>
      <td></td>
      <td>Model 2</td>
      <td></td>
    </tr>
    <tr>
      <td>Predictor</td>
      <td>Estimate</td>
      <td>Z</td>
      <td>p</td>
      <td>OR [95% CI]</td>
      <td>Estimate</td>
      <td>Z</td>
      <td>p</td>
      <td>OR [95% CI]</td>
    </tr>
    <tr>
      <td>Intercept</td>
      <td>-0.84 (0.11)</td>
      <td>-7.65</td>
      <td>&lt;.001</td>
      <td>0.43 [0.35, 0.53]</td>
      <td>-0.68 (0.12)</td>
      <td>-5.78</td>
      <td>&lt;.001</td>
      <td>0.51 [0.40, 0.64]</td>
    </tr>
    <tr>
      <td>Framing: Positive – Negative</td>
      <td>3.31 (0.14)</td>
      <td>24.14</td>
      <td>&lt;.001</td>
      <td>27.27 [20.97, 35.88]</td>
      <td>2.73 (0.21)</td>
      <td>12.96</td>
      <td>&lt;.001</td>
      <td>15.30 [10.23, 23.40]</td>
    </tr>
    <tr>
      <td>Default: No-Default – Opt-In</td>
      <td>-0.12 (0.15)</td>
      <td>-0.81</td>
      <td>.417</td>
      <td>0.89 [0.66, 1.19]</td>
      <td>-0.40 (0.18)</td>
      <td>-2.29</td>
      <td>.021</td>
      <td>0.66 [0.47, 0.94]</td>
    </tr>
    <tr>
      <td>Default: Opt-Out – Opt-In</td>
      <td>-0.05 (0.15)</td>
      <td>-0.35</td>
      <td>.724</td>
      <td>0.95 [0.71, 1.27]</td>
      <td>-0.29 (0.17)</td>
      <td>-1.66</td>
      <td>.096</td>
      <td>0.75 [0.54, 1.05]</td>
    </tr>
    <tr><td colspan="9"><strong>Interaction term:</strong></td></tr>
    <tr>
      <td>(Positive – Negative) × (No-Default–Opt-In)</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>1.00 (0.33)</td>
      <td>3.02</td>
      <td>.003</td>
      <td>2.74 [1.43, 5.35]</td>
    </tr>
    <tr>
      <td>(Positive – Negative) × (Opt-Out –Opt-In)</td>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
      <td>0.85 (0.33)</td>
      <td>2.57</td>
      <td>.010</td>
      <td>2.33 [1.23, 4.49]</td>
    </tr>
    <tr><td colspan="9"><strong>Note. Estimates represent the odds of the dependent variable = “1” vs. “0”. Standard errors are reported within the brackets.</strong></td></tr>
  </tbody>
</table>
