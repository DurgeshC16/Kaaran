"""Block lens (v2) wording for the three-part brief, registered into the shared registries in texts.py.

Same rules as texts.py: no digits in templates, figures only via placeholders, causal words only through the
STRONG-gated verifier. All Marathi needs native-speaker review.
"""

from __future__ import annotations

from . import texts as X

BLOCK_SECTIONS = ("attention", "why", "action")
BLOCK_HEADINGS = {
    "attention": ("लक्ष देण्याची गरज", "What needs attention"),
    "why": ("असे का होत असावे", "Why it may be happening"),
    "action": ("काय करावे", "What to do"),
    "appendix": ("इतर तपासण्या", "Other checks"),
}
BLOCK_TITLE = ("केंद्रनिहाय पुरावा अहवाल", "Cluster Evidence Brief")

X.BADGES.update({
    ("RISK", "STRONG"): ("तातडीने लक्ष द्या", "Needs attention now"),
    ("RISK", "WEAK"): ("लक्ष ठेवा", "Watch closely"),
})
X.HORIZONS.update({
    "next_baithak": ("पुढील बैठकीत", "at the next review meeting"),
    "before_november": ("नोव्हेंबरपूर्वी", "before November"),
    "before_next_duty": ("पुढील निवडणूक कामापूर्वी", "before the next duty order"),
})
X.TEXT_KEYS.update({
    "subject.overall": ("गणित व भाषा", "maths and language"),
    "comp.M1": ("संख्याज्ञान", "number sense"),
    "comp.M2": ("स्थानिक किंमत", "place value"),
    "comp.M3": ("बेरीज", "addition"),
    "comp.M4": ("वजाबाकी", "subtraction"),
    "comp.M5": ("आकार व आकृतिबंध", "shapes and patterns"),
    "comp.L1": ("अक्षर-ध्वनी ओळख", "letter-sound knowledge"),
    "comp.L2": ("शब्द वाचन", "word reading"),
    "comp.L3": ("प्रवाही वाचन", "reading fluency"),
    "comp.L4": ("वाचन आकलन", "reading comprehension"),
    "constraint.staffing_gap": ("एक शिक्षक कमी", "one teacher short"),
    "constraint.support_gap": ("केंद्रप्रमुख भेटी कमी", "few Kendra Pramukh visits"),
    "question.block_attention": ("कोणत्या केंद्रांकडे लक्ष द्यावे", "which clusters need attention"),
})
X.CAVEATS.update({
    "caveat.small_schools_noise": (
        "शाळा लहान असल्याने एका शाळेचे निकाल वर्षानुवर्षे बदलतात; म्हणून केंद्रपातळीवर तुलना केली आहे.",
        "Schools are small, so one school's results swing from year to year; the comparison is made at cluster level."),
    "caveat.positive_deviants_separate": (
        "अडचण असूनही प्रगती केलेल्या शाळा या तुलनेतून वेगळ्या ठेवल्या आहेत.",
        "Schools that improved despite the same constraint are shown separately."),
})

TEMPLATES = {
    # A: what needs attention
    "risk.cluster_drop": (
        "[[cluster]] केंद्रातील [[schools]] शाळांचा [[subject]] निकाल तालुक्यातील इतर शाळांपेक्षा [[drop]] गुणांनी जास्त घसरला ([[period]]).",
        "[[cluster]]: across its [[schools]] schools, [[subject]] results fell [[drop]] points more than other schools in the block ([[period]])."),
    "risk.cluster_pocket": (
        "[[cluster]] केंद्रातील [[schools]] पैकी [[pocket]] शाळांचा निकाल मोठ्या प्रमाणात घसरला; केंद्राची सरासरी घट इतर शाळांपेक्षा [[drop]] गुणांनी जास्त आहे ([[period]]).",
        "[[cluster]]: [[pocket]] of its [[schools]] schools fell sharply; the cluster fell [[drop]] points more than other schools on average ([[period]])."),
    "risk.cluster_absence": (
        "[[cluster]] केंद्रातील [[low]] शाळांमध्ये [[period]] या काळात बहुतेक महिने हजेरी [[threshold]] पेक्षा कमी होती.",
        "[[cluster]]: in [[low]] schools, attendance was below [[threshold]] in most of [[period]]."),
    "risk.cluster_level": (
        "[[cluster]] केंद्राचा सध्याचा निकाल [[level]] आहे, तर तालुक्यातील केंद्रांचा मध्य [[block_level]] आहे.",
        "[[cluster]]: its current result is [[level]], against a middle value of [[block_level]] for the block's clusters."),
    "data.cluster_flat": (
        "[[cluster]] केंद्रातील [[flagged]] शाळांनी [[period]] या काळात दर महिन्याला पूर्ण हजेरी नोंदवली, पण त्यांचा निकाल कमी आहे. या नोंदी अविश्वसनीय दिसतात आणि तपासाव्या लागतील.",
        "[[cluster]]: [[flagged]] schools reported full attendance every month in [[period]], yet their results are low. These records look unreliable and need checking."),
    "data.cluster_insufficient": (
        "[[cluster]] केंद्रातील [[missing]] शाळांची हजेरी किंवा मूल्यमापनाची माहिती अपूर्ण आहे. त्यामुळे या केंद्राबद्दल आत्ता निष्कर्ष काढता येत नाही.",
        "[[cluster]]: attendance or assessment data is missing for [[missing]] schools, so this cluster cannot be judged yet."),
    "data.cleared_block": (
        "[[schools]] शाळांची हजेरी कमी आहे, पण ती नैसर्गिक चढ-उतारासारखी दिसते. त्या शाळांवर कोणताही संशय नाही.",
        "[[schools]] schools have low attendance, but it looks like natural variation. They were checked and are not flagged."),
    # B: why it may be happening
    "diag.staffing": (
        "[[cluster]] केंद्रातील [[exposed]] शाळांमध्ये या वर्षी ([[period]]) एक शिक्षक कमी झाला आणि अनेक वर्ग एकाच शिक्षकाकडे आहेत. या शाळांचा निकाल इतर शाळांपेक्षा [[diff]] गुणांनी जास्त घसरला.",
        "[[cluster]]: [[exposed]] schools lost a teacher this year ([[period]]) and now have several classes per teacher. Their results fell [[diff]] points more than other schools."),
    "diag.support": (
        "[[cluster]] केंद्रात केंद्रप्रमुखांच्या भेटी दर शाळेला दरमहा [[before]] वरून [[now]] वर आल्या. शिक्षक उपलब्ध आहेत, तरीही या केंद्राचा गणिताचा निकाल इतर शाळांपेक्षा [[diff]] गुणांनी जास्त घसरला.",
        "[[cluster]]: Kendra Pramukh visits fell from [[before]] to [[now]] per school per month. Teachers are in place, yet its maths results fell [[diff]] points more than other schools."),
    "diag.absence": (
        "[[cluster]] केंद्रातील [[exposed]] शाळांमध्ये हजेरी मागील वर्षापेक्षा कमी झाली आणि त्याच शाळांचा निकाल इतर शाळांपेक्षा [[diff]] गुणांनी जास्त घसरला.",
        "[[cluster]]: attendance fell in [[exposed]] schools compared with last year, and the same schools' results fell [[diff]] points more than other schools."),
    "diag.migration": (
        "[[cluster]] केंद्रातील [[mig]] शाळांमध्ये दर वर्षी नोव्हेंबर ते मार्च हजेरी सुमारे [[gap]] गुणांनी घटते. कुटुंबे हंगामी कामासाठी स्थलांतर करत असल्याचे हे चिन्ह आहे. अंतिम मूल्यमापनात या शाळांचा निकाल कमी येतो.",
        "[[cluster]]: in [[mig]] schools attendance drops by about [[gap]] points every November to March, a sign that families migrate for seasonal work. Their endline results are lower."),
    "diag.competency": (
        "[[cluster]] केंद्रात [[compa]] हा भाग सर्वात कमकुवत आहे ([[compa_level]], तर तालुक्यात [[compa_block]]).",
        "[[cluster]]: the weakest area is [[compa]] ([[compa_level]] against [[compa_block]] in the block)."),
    "diag.competency2": (
        "[[cluster]] केंद्रात [[compa]] ([[compa_level]], तालुक्यात [[compa_block]]) आणि [[compb]] ([[compb_level]], तालुक्यात [[compb_block]]) हे भाग सर्वात कमकुवत आहेत.",
        "[[cluster]]: the weakest areas are [[compa]] ([[compa_level]] against [[compa_block]] in the block) and [[compb]] ([[compb_level]] against [[compb_block]])."),
    "diag.no_clear_pattern": (
        "[[cluster]] केंद्रात शिक्षक, केंद्रप्रमुख भेटी, हजेरी, स्थलांतर किंवा डेटा यापैकी कशानेही घसरण स्पष्ट होत नाही; शिक्षक उपलब्ध आहेत.",
        "[[cluster]]: none of the checks (teachers, Kendra Pramukh visits, attendance, migration, data) explains the fall; teachers are available."),
    "diag.duty_ruled_out": (
        "[[period]] मध्ये निवडणूक कामात शिक्षकांचे सरासरी [[days]] दिवस गेले; हे सर्व केंद्रांमध्ये झाले. असे काम असलेल्या [[n]] केंद्रांपैकी [[no_drop]] केंद्रांचा निकाल घसरला नाही, म्हणून हे मुख्य कारण दिसत नाही.",
        "Poll duty in [[period]] took about [[days]] days per teacher in every cluster. [[no_drop]] of the [[n]] clusters with the same duty did not fall, so it does not look like the main reason."),
    "diag.duty_associated": (
        "[[period]] मध्ये निवडणूक कामात शिक्षकांचे सरासरी [[days]] दिवस गेले, आणि अनेक केंद्रांचा निकाल त्याच काळात घसरला. याचा संबंध दिसतो.",
        "Poll duty in [[period]] took about [[days]] days per teacher, and many clusters fell in the same period. The two look linked."),
    "learn.positive_deviant": (
        "[[cluster]] केंद्रातील [[pd]] शाळेलाही हीच अडचण होती ([[constraint]]), तरीही तिचा निकाल इतर शाळांपेक्षा [[gain]] गुणांनी जास्त वाढला. तिथे काय वेगळे केले जाते ते शिकण्यासारखे आहे.",
        "[[pd]] school in [[cluster]] faced the same constraint ([[constraint]]), yet its results rose [[gain]] points more than other schools. What it does differently is worth learning."),
    "twin.block": (
        "[[twin]] तालुका आकार आणि शिक्षक-विद्यार्थी प्रमाणात [[focus]] तालुक्यासारखाच आहे, तरीही तिथे निकाल [[twin_change]] गुणांनी वाढला, तर [[focus]] तालुक्यात [[focus_change]] गुणांनी घटला. [[decoy]] तालुकाही सारखाच आहे, पण तिथे सुधारणा झाली नाही.",
        "[[twin]] block is similar to [[focus]] in size and pupil-teacher ratio, yet its results rose [[twin_change]] points while [[focus]] fell [[focus_change]]. [[decoy]] is also similar but did not improve."),
    # C: what to do
    "action.redeploy": (
        "कमी विद्यार्थी-प्रति-शिक्षक असलेल्या [[surplus]] शाळांमधून एक शिक्षक [[cluster]] केंद्रातील शिक्षक कमी असलेल्या शाळांमध्ये समायोजित करावा.",
        "Redeploy a teacher from the [[surplus]] schools with few pupils per teacher to the schools short of a teacher in [[cluster]]."),
    "action.guest_teacher": (
        "[[cluster]] केंद्रातील शिक्षक कमी असलेल्या [[gap]] शाळांसाठी तासिका किंवा कंत्राटी शिक्षकाची मागणी करावी.",
        "Request a guest or contract teacher for the [[gap]] schools short of a teacher in [[cluster]]."),
    "action.multigrade_support": (
        "[[cluster]] केंद्रातील [[multi]] बहुवर्ग शाळांना भेट देऊन बहुवर्ग अध्यापनाचे पाठ नियोजन आणि स्तरानुसार गट करण्यास मदत करावी.",
        "Visit the [[multi]] multigrade schools in [[cluster]] with multigrade lesson plans and help group children by level."),
    "action.mentoring_cycle": (
        "पुढील महिनाभर [[cluster]] केंद्रातील सर्व [[schools]] शाळांना दर आठवड्याला वर्ग-भेट द्यावी आणि [[compa]] या क्षमतेवर लक्ष द्यावे.",
        "For the next month, visit classrooms in all [[schools]] schools of [[cluster]] every week, focusing on [[compa]]."),
    "action.targeted_training": (
        "[[cluster]] केंद्रातील शिक्षकांसाठी [[compa]] या क्षमतेवर केंद्रस्तरीय शिक्षण परिषद घ्यावी (शेवटचे प्रशिक्षण: [[last]]).",
        "Hold a cluster-level teacher session on teaching [[compa]] for [[cluster]] (last training: [[last]])."),
    "action.accountability_review": (
        "पुढील बैठकीत [[cluster]] केंद्राचा आढावा घ्यावा: शाळानिहाय उद्दिष्टे ठरवावीत आणि महिनाभर मुख्याध्यापकांसोबत साप्ताहिक आढावा घ्यावा.",
        "Review [[cluster]] at the next review meeting: set school-wise targets and hold a weekly review call with head teachers for a month."),
    "action.attendance_drive": (
        "[[cluster]] केंद्रातील [[exposed]] शाळांत जास्त दिवस गैरहजर असणाऱ्या मुलांच्या घरी मुख्याध्यापक आणि शाळा व्यवस्थापन समितीने भेटी द्याव्यात.",
        "Head teachers and SMC members visit the homes of children absent for many days in the [[exposed]] schools of [[cluster]]."),
    "action.migration_tracking": (
        "[[cluster]] केंद्रातील [[mig]] शाळांतून स्थलांतर करणाऱ्या मुलांची यादी करावी, हंगामी वसतिगृह किंवा स्थलांतराच्या ठिकाणी शिक्षणाची व्यवस्था करावी आणि परत आल्यावर सेतू वर्ग घ्यावेत.",
        "List the children who migrate from the [[mig]] schools in [[cluster]], arrange seasonal hostels or schooling at the destination, and run bridge classes when they return."),
    "action.verify_registers_cluster": (
        "[[cluster]] केंद्रातील [[flagged]] शाळांचे हजेरीपट प्रत्यक्ष भेट देऊन तपासावेत; तपासणी होईपर्यंत त्यांच्या निकालावर निर्णय घेऊ नये.",
        "Check the attendance registers of the [[flagged]] flagged schools in [[cluster]] in person; do not judge their results until checked."),
    "action.collect_missing_cluster": (
        "[[cluster]] केंद्रातील [[missing]] शाळांची हजेरी आणि मूल्यमापनाची अपूर्ण माहिती पूर्ण करून घ्यावी.",
        "Get the missing attendance and assessment data completed for the [[missing]] schools in [[cluster]]."),
    "action.peer_visit": (
        "शिक्षक कमी असलेल्या शाळांतील शिक्षकांनी अडचण असूनही प्रगती केलेल्या [[pd]] शाळेला भेट द्यावी आणि तिथली पद्धत नोंदवावी.",
        "Teachers from the schools facing the same shortage visit the [[pd]] school that improved despite it, and note down its practice."),
    "action.duty_rotation": (
        "मूल्यमापनाच्या काळात निवडणूक कामाचे वाटप फिरते ठेवावे किंवा सवलत मागावी.",
        "Rotate poll-duty assignments around assessment windows, or request an exemption."),
    "action.exposure_visit_block": (
        "[[twin]] तालुक्याला अभ्यास भेट आयोजित करावी आणि तिथे काय वेगळे केले ते समजून घ्यावे.",
        "Organise an exposure visit to [[twin]] block to learn what it did differently."),
}
X.TEMPLATES.update(TEMPLATES)

ACTION_TEMPLATE = {"A1": "action.redeploy", "A2": "action.guest_teacher", "A3": "action.multigrade_support",
                   "A4": "action.mentoring_cycle", "A5": "action.targeted_training", "A6": "action.accountability_review",
                   "A7": "action.attendance_drive", "A8": "action.migration_tracking", "A9": "action.duty_rotation",
                   "A10": "action.verify_registers_cluster", "A11": "action.collect_missing_cluster", "A12": "action.peer_visit",
                   "A13": "action.exposure_visit_block"}
