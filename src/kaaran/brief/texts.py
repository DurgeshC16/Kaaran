"""Fixed wording rendered by code: headings, badges, owners, months, text keys, caveats and fallback templates.

All Marathi text here needs native-speaker review (see data/samples/brief_seed*.md). Templates use [[param]]
for a finding's params; they are expanded to {{n:}}, {{e:}}, {{s:}}, {{p:}} placeholders before filling, so the
template brief and the LLM brief go through the same filler and verifier. No digits appear in any template.
"""

from __future__ import annotations

SECTION_HEADINGS = {
    "trend": ("कल", "Trend"),
    "election_check": ("निवडणूक कारण तपासले", "Election-duty check"),
    "main_cause": ("संभाव्य मुख्य कारण", "Probable main cause"),
    "twin": ("जुळा तालुका", "Twin taluka"),
    "data_warning": ("डेटा इशारा", "Data warning"),
    "action": ("सुचवलेली कृती", "Suggested action"),
    "appendix": ("इतर तपासण्या", "Other checks"),
}
REQUIRED_SECTIONS = ("trend", "election_check", "main_cause", "twin", "data_warning", "action")
NOT_APPLICABLE = ("या प्रश्नासाठी या विभागात कोणताही निष्कर्ष नाही.", "No finding in this section for this question.")

BADGES = {  # (type, label) -> (mr, en); label.<TYPE>.<LABEL>
    ("TREND", "STRONG"): ("ठाम पुरावा", "Strong evidence"),
    ("TREND", "WEAK"): ("कमकुवत पुरावा", "Weak evidence"),
    ("TREND", "INSUFFICIENT"): ("पुरेसा डेटा नाही", "Not enough data"),
    ("CAUSE", "STRONG"): ("ठाम पुरावा", "Strong evidence"),
    ("CAUSE", "WEAK"): ("कमकुवत कारण", "Weak cause"),
    ("CAUSE", "RULED_OUT"): ("संबंध आढळला नाही", "No link found"),
    ("CAUSE", "INSUFFICIENT"): ("पुरेसा डेटा नाही", "Not enough data"),
    ("TWIN", "LEARN_FROM"): ("यांच्याकडून शिका", "Learn from"),
    ("TWIN", "INSUFFICIENT"): ("पुरेसा डेटा नाही", "Not enough data"),
    ("DATA", "RED_FLAG"): ("धोक्याची सूचना", "Red flag"),
    ("DATA", "INSUFFICIENT"): ("पुरेसा डेटा नाही", "Not enough data"),
    ("DATA", "CLEARED"): ("तपासले, ठीक आहे", "Checked, fine"),
    ("ACTION", "ACTION"): ("कृती", "Action"),
}
ACTORS = {
    "DEO": ("जिल्हा शिक्षणाधिकारी (DEO)", "District Education Officer (DEO)"),
    "BEO": ("गट शिक्षणाधिकारी (BEO)", "Block Education Officer (BEO)"),
    "KENDRA_PRAMUKH": ("केंद्रप्रमुख", "Kendra Pramukh (cluster head)"),
}
HORIZONS = {"this_week": ("या आठवड्यात", "this week"), "this_month": ("या महिन्यात", "this month")}
BANNER = ("कृत्रिम (SYNTHETIC) डेमो डेटा - ही खरी आकडेवारी किंवा खरा निष्कर्ष नाही.",
          "SYNTHETIC demo data - not real figures and not a real finding.")
TITLE = ("पुरावा अहवाल", "Evidence Brief")
QUESTION = {"question.why_decline": ("{taluka} तालुक्याचा गणिताचा निकाल का घसरला?", "Why did {taluka}'s maths results fall?")}
MONTHS_MR = ["", "जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून", "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर", "डिसेंबर"]
MONTHS_EN = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
TEXT_KEYS = {
    "subject.maths": ("गणित", "maths"),
    "subject.language": ("भाषा", "language"),
    "hypothesis.vacancy": ("शिक्षकांच्या रिक्त जागा", "teacher vacancies"),
    "hypothesis.election": ("निवडणूक काम", "election duty"),
    "hypothesis.infrastructure": ("पायाभूत सुविधा", "infrastructure"),
    "hypothesis.attendance": ("हजेरी", "attendance"),
    "question.why_decline": ("निकाल का घसरला", "why results fell"),
}

CAVEATS = {
    "caveat.associated_not_caused": ("हा संबंध आहे; कारण सिद्ध झालेले नाही.", "This is an association; it does not prove a cause."),
    "caveat.concentrated_in_few_schools": ("घसरण काही शाळांमध्ये एकवटलेली आहे ([[schools]] शाळा).",
                                           "The decline is concentrated in a few schools ([[schools]] schools)."),
    "caveat.poverty_not_available": ("दारिद्र्याची आकडेवारी उपलब्ध नसल्याने तुलना आकार आणि पटसंख्येवर आधारित आहे.",
                                     "No poverty data was available, so the comparison uses size and enrolment only."),
    "caveat.static_infra_snapshot": ("पायाभूत सुविधांची माहिती एकाच वर्षाची आहे.", "Infrastructure data is a single-year snapshot."),
    "caveat.small_sample": ("नमुना लहान आहे.", "The sample is small."),
    "caveat.flagged_data_excluded": ("संशयास्पद नोंदी विश्लेषणातून वगळल्या आहेत.", "Suspicious records were left out of the analysis."),
}
SKIP_CAVEATS = {"caveat.synthetic_data"}  # the banner already says it

TEMPLATES = {  # template_key -> (mr, en)
    "trend.decline_rank": (
        "[[period]] या काळात [[taluka]] तालुक्याचा गणिताचा सरासरी गुण [[score_from]] वरून [[score_to]] वर आला. ही [[change]] गुणांची घसरण आहे. जिल्ह्यातील क्रमांक [[rank_from]] वरून [[rank_to]] वर गेला.",
        "Over [[period]], [[taluka]]'s average maths score fell from [[score_from]] to [[score_to]], a drop of [[change]] points. Its rank in the district moved from [[rank_from]] to [[rank_to]]."),
    "trend.rise_rank": (
        "[[period]] या काळात [[taluka]] तालुक्याचा गणिताचा सरासरी गुण [[score_from]] वरून [[score_to]] पर्यंत वाढला. ही [[change]] गुणांची वाढ आहे. जिल्ह्यातील क्रमांक [[rank_from]] वरून [[rank_to]] वर आला.",
        "Over [[period]], [[taluka]]'s average maths score rose from [[score_from]] to [[score_to]], a gain of [[change]] points. Its rank in the district moved from [[rank_from]] to [[rank_to]]."),
    "trend.decline_weak": (
        "[[period]] या काळात [[taluka]] तालुक्याचा सरासरी गुण [[score_from]] वरून [[score_to]] वर आला ([[change]] गुणांनी कमी). पण ही घसरण सर्व वर्षांत स्पष्ट दिसत नाही.",
        "Over [[period]], [[taluka]]'s average score went from [[score_from]] to [[score_to]] ([[change]] points lower), but the drop is not clear in every year."),
    "trend.no_clear_change": (
        "[[period]] या काळात [[taluka]] तालुक्याच्या सरासरी गुणांत स्पष्ट बदल दिसत नाही ([[change]] गुणांचा फरक).",
        "There is no clear change in [[taluka]]'s average score over [[period]] (a difference of [[change]] points)."),
    "cause.election.similar_blocks_no_drop": (
        "[[period]] मध्ये [[taluka]] तालुक्याचा गुण [[focus_change]] गुणांनी कमी झाला. पण त्याच वर्षी निवडणूक कामाचा मोठा भार असलेल्या इतर [[similar]] तालुक्यांपैकी [[n_similar_no_drop]] तालुक्यांचे गुण घसरले नाहीत. म्हणून निवडणूक काम हे घसरणीचे कमकुवत स्पष्टीकरण आहे.",
        "In [[period]], [[taluka]]'s score went down by [[focus_change]] points. But of the [[similar]] other talukas with the same heavy election duty that year, [[n_similar_no_drop]] did not drop. Election duty is therefore a weak explanation for the fall."),
    "cause.election.associated": (
        "[[period]] मध्ये निवडणूक कामाचा मोठा भार असलेल्या बहुतेक तालुक्यांचे गुणही घसरले. निवडणूक कामाचा घसरणीशी संबंध दिसतो, पण ते कारण असल्याचे सिद्ध होत नाही.",
        "In [[period]], most talukas with heavy election duty also dropped. Election duty is associated with the fall, but that does not show it caused it."),
    "cause.election.no_link": (
        "निवडणूक कामाच्या [[period]] वर्षात [[taluka]] तालुक्याचे गुण घसरले नाहीत ([[focus_change]] गुणांचा बदल). निवडणूक कामाचा संबंध आढळला नाही.",
        "In the election-duty year [[period]], [[taluka]]'s scores did not drop (a change of [[focus_change]] points). No link to election duty was found."),
    "cause.vacancy.concentrated": (
        "[[since]] पासून गणित शिक्षक नसलेल्या [[schools]] शाळांचे गुण सरासरी [[group_change]] गुणांनी घसरले, तर इतर शाळांचे फक्त [[others_change]] गुणांनी. तालुक्याच्या एकूण घसरणीपैकी [[share_of_decline]] घसरण याच शाळांमध्ये आहे. गणित शिक्षकांच्या रिक्त जागा हे घसरणीचे संभाव्य मुख्य कारण आहे.",
        "Since [[since]], the [[schools]] schools without a maths teacher fell by [[group_change]] points on average, against [[others_change]] points for the other schools. These schools account for [[share_of_decline]] of the taluka's decline. The vacant maths posts are the probable main cause."),
    "cause.vacancy.associated": (
        "गणित शिक्षक नसलेल्या [[schools]] शाळांचे गुण [[group_change]] गुणांनी बदलले, तर इतर शाळांचे [[others_change]] गुणांनी. रिक्त जागांचा घसरणीशी संबंध दिसतो, पण ते मुख्य कारण असल्याचे सिद्ध होत नाही.",
        "The [[schools]] schools without a maths teacher changed by [[group_change]] points, against [[others_change]] points for the other schools. Vacancies are associated with the fall, but that does not show they are the main cause."),
    "cause.vacancy.no_link": (
        "गणित शिक्षक नसलेल्या शाळा आणि इतर शाळा यांच्या गुणांतील बदलात स्पष्ट फरक नाही ([[group_change]] विरुद्ध [[others_change]] गुण). संबंध आढळला नाही.",
        "There is no clear difference between schools without a maths teacher and the other schools ([[group_change]] against [[others_change]] points). No link was found."),
    "cause.infra.no_link": (
        "पायाभूत सुविधा आणि गुणांतील बदल यांचा संबंध आढळला नाही (सहसंबंध [[r]]). सर्वात कमी सुविधा असलेल्या [[lowest_infra_taluka]] तालुक्याचे गुण जवळजवळ स्थिर राहिले ([[lowest_infra_change]] गुणांचा बदल).",
        "No link was found between infrastructure and the change in scores (correlation [[r]]). [[lowest_infra_taluka]], which has the weakest infrastructure, stayed almost level (a change of [[lowest_infra_change]] points)."),
    "cause.infra.associated": (
        "पायाभूत सुविधा आणि गुणांतील बदल यांच्यात संबंध दिसतो (सहसंबंध [[r]]), पण ते कारण असल्याचे सिद्ध होत नाही.",
        "Infrastructure is associated with the change in scores (correlation [[r]]), but that does not show it is a cause."),
    "cause.attendance.no_link": (
        "हजेरी आणि गुणांतील बदल यांचा संबंध आढळला नाही (सहसंबंध [[r]]).",
        "No link was found between attendance and the change in scores (correlation [[r]])."),
    "cause.attendance.associated": (
        "हजेरी आणि गुणांतील बदल यांच्यात संबंध दिसतो (सहसंबंध [[r]]), पण ते कारण असल्याचे सिद्ध होत नाही.",
        "Attendance is associated with the change in scores (correlation [[r]]), but that does not show it is a cause."),
    "cause.inconclusive": (
        "[[hypothesis]] याबद्दल ठोस निष्कर्ष काढण्यासाठी पुरेसा पुरावा नाही.",
        "There is not enough evidence to judge [[hypothesis]]."),
    "twin.learn_from": (
        "[[twin]] तालुका आकार, पटसंख्या आणि दारिद्र्य प्रमाणात [[focus]] तालुक्यासारखा आहे ([[n_schools_twin]] विरुद्ध [[n_schools_focus]] शाळा). तरीही त्याचे गुण [[twin_change]] गुणांनी वाढले आणि जिल्ह्यातील क्रमांक [[twin_rank_from]] वरून [[twin_rank_to]] वर आला.",
        "[[twin]] is similar to [[focus]] in size, enrolment and poverty ([[n_schools_twin]] against [[n_schools_focus]] schools). Yet its score rose by [[twin_change]] points and its district rank moved from [[twin_rank_from]] to [[twin_rank_to]]."),
    "twin.decoy": (
        "[[decoy]] तालुकाही सारखा आहे, पण त्याचे गुण वाढले नाहीत ([[decoy_change]] गुणांचा बदल).",
        "[[decoy]] is also similar, but its score did not rise (a change of [[decoy_change]] points)."),
    "twin.none_found": (
        "[[focus]] तालुक्यासारखा आणि प्रगती केलेला तालुका आढळला नाही.",
        "No taluka similar to [[focus]] that improved was found."),
    "data.flat_attendance": (
        "[[taluka]] तालुक्यातील [[schools]] शाळांनी [[months]] या काळात सलग [[n_months]] महिने पूर्ण हजेरी नोंदवली. ही नोंद अविश्वसनीय दिसते. तालुक्यातील [[share]] शाळा अशा आहेत, तर जिल्ह्यात इतरत्र फक्त [[rest_share]].",
        "[[schools]] schools in [[taluka]] reported full attendance for [[n_months]] months in a row ([[months]]). This looks unreliable: [[share]] of the taluka's schools, against [[rest_share]] elsewhere in the district."),
    "data.insufficient": (
        "[[taluka]] तालुक्यातील [[schools]] शाळांची हजेरी किंवा गुणांची माहिती अपुरी आहे ([[share]] शाळा). या तालुक्याबद्दल निष्कर्ष काढण्यापूर्वी माहिती पूर्ण करणे गरजेचे आहे.",
        "Attendance or score data is incomplete for [[schools]] schools in [[taluka]] ([[share]] of its schools). The data should be completed before drawing conclusions about this taluka."),
    "data.cleared_low_attendance": (
        "[[taluka]] तालुक्यातील [[schools]] शाळांची हजेरी कमी आहे, पण ती नैसर्गिक चढ-उतारासारखी दिसते. त्या शाळांवर कोणताही संशय नाही.",
        "[[schools]] schools in [[taluka]] have low attendance, but it looks like natural variation. They were checked and are not flagged."),
    "action.redeploy_teachers": (
        "गणित शिक्षक नसलेल्या [[schools]] शाळांमध्ये गणित शिक्षकांची पुनर्नियुक्ती करावी.",
        "Redeploy maths teachers to the [[schools]] schools that have none."),
    "action.exposure_visit": (
        "[[twin]] तालुक्याला अभ्यास भेट आयोजित करावी आणि तिथे काय वेगळे केले ते समजून घ्यावे.",
        "Organise an exposure visit to [[twin]] to learn what it did differently."),
    "action.verify_registers": (
        "पूर्ण हजेरी नोंदवलेल्या [[schools]] शाळांचे हजेरीपट प्रत्यक्ष भेट देऊन तपासावेत.",
        "Check the attendance registers of the [[schools]] schools with full attendance in person."),
    "action.collect_missing_data": (
        "[[schools]] शाळांची अपुरी माहिती पूर्ण करून घ्यावी.",
        "Get the missing data completed for the [[schools]] schools."),
}
