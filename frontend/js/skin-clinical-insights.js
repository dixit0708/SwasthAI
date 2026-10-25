/**
 * SwasthAI - Skin Disease Clinical Insights Configuration
 * 
 * Provides short, non-diagnostic educational overviews for each of the 23 dermatological
 * category groups from the DermNet reference taxonomy.
 * 
 * IMPORTANT:
 * - Each category includes a TODO to verify against authoritative dermatological
 *   sources such as DermNet NZ (dermnetnz.org) or the American Academy of Dermatology (aad.org).
 * - Text must remain purely educational, non-diagnostic, and conservative.
 */

const SKIN_CLINICAL_INSIGHTS = {
    'Acne and Rosacea Photos': {
        // TODO: Verify summary against DermNet NZ or AAD (Acne vulgaris & Rosacea).
        title: 'Acne and Rosacea',
        whatItIs: 'A common group of inflammatory conditions involving the skin\'s oil (sebaceous) glands and hair follicles, frequently presenting as blemishes, blackheads, pustules, or persistent facial redness.',
        whenToSeeDoctor: 'Consider seeing a doctor or dermatologist if over-the-counter skincare is ineffective, if breakouts cause pain or deep cysts, or to prevent persistent scarring and pigmentation changes.'
    },

    'Actinic Keratosis Basal Cell Carcinoma and other Malignant Lesions': {
        // TODO: Verify summary against DermNet NZ or AAD (Actinic keratosis & Non-melanoma skin cancer).
        title: 'Actinic Keratosis, Basal Cell Carcinoma & Malignant Lesions',
        isMalignantCategory: true,
        whatItIs: 'A broad category covering sun-induced changes ranging from rough, scaly precancerous spots (actinic keratoses) to non-melanoma skin malignancies such as basal cell carcinoma or squamous cell carcinoma.',
        whenToSeeDoctor: 'Any firm, scaly, non-healing sore, pearly bump, or spot that bleeds easily or grows steadily should be formally examined by a qualified dermatologist or physician.'
    },

    'Atopic Dermatitis Photos': {
        // TODO: Verify summary against DermNet NZ or AAD (Atopic eczema).
        title: 'Atopic Dermatitis (Eczema)',
        whatItIs: 'A chronic, pruritic (itchy) inflammatory skin condition associated with skin barrier disruption, often presenting as dry, red, irritated patches in skin flexures such as the elbows and knees.',
        whenToSeeDoctor: 'Consult a healthcare professional if itching disrupts sleep, if home moisturizing routines do not relieve discomfort, or if cracked skin shows signs of weeping or bacterial infection.'
    },

    'Bullous Disease Photos': {
        // TODO: Verify summary against DermNet NZ or AAD (Immunobullous diseases & blister disorders).
        title: 'Bullous (Blistering) Disease',
        whatItIs: 'A group of disorders characterized by fluid-filled blisters (bullae) on the skin surface, ranging from contact or allergic blistering to less common autoimmune blistering conditions.',
        whenToSeeDoctor: 'Widespread blistering, blisters that form without obvious friction or burn, or blisters involving the eyes, mouth, or mucous membranes require prompt in-person medical evaluation.'
    },

    'Cellulitis Impetigo and other Bacterial Infections': {
        // TODO: Verify summary against DermNet NZ or AAD (Bacterial skin infections).
        title: 'Cellulitis, Impetigo & Bacterial Infections',
        whatItIs: 'Bacterial infections affecting either the superficial skin layers (such as honey-crusted impetigo) or the deeper dermis and underlying subcutaneous tissue (cellulitis).',
        whenToSeeDoctor: 'Prompt medical attention is essential if you observe expanding warm redness, tenderness, swelling, pus, or if the skin symptoms are accompanied by fever or chills.'
    },

    'Eczema Photos': {
        // TODO: Verify summary against DermNet NZ or AAD (Dermatitis and eczema overview).
        title: 'Eczema & Dermatitis Spectrum',
        whatItIs: 'An umbrella term for various inflammatory skin patterns causing dry, red, itchy, or flaky patches that may flare up in response to environmental triggers, moisture loss, or irritants.',
        whenToSeeDoctor: 'Consult a doctor if standard gentle moisturizers do not bring relief, if the rash is spreading, or if scratching has caused broken or infected skin.'
    },

    'Exanthems and Drug Eruptions': {
        // TODO: Verify summary against DermNet NZ or AAD (Adverse cutaneous drug reactions & viral exanthems).
        title: 'Allergic Skin Eruptions & Exanthems',
        whatItIs: 'Widespread, symmetrical skin eruptions often triggered by a viral infection (viral exanthem) or an adverse reaction to a recently ingested medication.',
        whenToSeeDoctor: 'Seek medical advice promptly, particularly if the rash developed after starting a new medicine. Seek urgent emergency care if you experience breathing difficulty, facial swelling, or mouth sores.'
    },

    'Hair Loss Photos Alopecia and other Hair Diseases': {
        // TODO: Verify summary against DermNet NZ or AAD (Alopecia areata & hair disorders).
        title: 'Hair Loss (Alopecia) & Scalp Disorders',
        whatItIs: 'Conditions that affect the hair follicles and scalp, including patchy autoimmune thinning (alopecia areata), progressive shedding, or inflammatory scalp dermatoses.',
        whenToSeeDoctor: 'Consult a dermatologist if hair loss is sudden, patchy, accompanied by scalp burning, redness, or scarring, so an early evaluation of follicle health can be performed.'
    },

    'Herpes HPV and other STDs Photos': {
        // TODO: Verify summary against DermNet NZ or AAD (Cutaneous viral infections & herpesviridae).
        title: 'Herpes, HPV & Viral Lesions',
        whatItIs: 'Skin and mucosal manifestations caused by common viral agents, including herpes simplex (cold sores or clustered blisters) and human papillomavirus (viral warts).',
        whenToSeeDoctor: 'A healthcare provider can confirm the visual pattern, prescribe targeted antiviral treatments, and advise on symptom comfort and preventing transmission.'
    },

    'Light Diseases and Disorders of Pigmentation': {
        // TODO: Verify summary against DermNet NZ or AAD (Pigmentary disorders & photodermatology).
        title: 'Pigmentation Disorders & Photodermatoses',
        whatItIs: 'Variations in skin melanin levels, including lighter depigmented patches (such as vitiligo), darker patches (melasma), or unusual cutaneous sensitivity to sunlight.',
        whenToSeeDoctor: 'Schedule an evaluation if pigment loss or darkening is expanding, unexplained, or if exposure to moderate sunlight triggers an unexpected rash or burning sensation.'
    },

    'Lupus and other Connective Tissue diseases': {
        // TODO: Verify summary against DermNet NZ or AAD (Cutaneous lupus erythematosus).
        title: 'Lupus & Connective Tissue Diseases',
        whatItIs: 'Cutaneous presentations associated with autoimmune or connective tissue conditions, which can manifest as facial erythema (malar pattern), round scaly plaques, or sun-sensitive rashes.',
        whenToSeeDoctor: 'A comprehensive medical consultation is advisable if persistent facial rashes coincide with joint pain, unusual fatigue, hair thinning, or heightened sun sensitivity.'
    },

    'Melanoma Skin Cancer Nevi and Moles': {
        // TODO: Verify summary against DermNet NZ or AAD (Melanocytic nevi & melanoma warning signs).
        title: 'Melanoma, Skin Cancer, Nevi & Moles',
        isMalignantCategory: true,
        whatItIs: 'A category covering benign pigment spots (common moles and nevi) as well as melanoma, a serious form of skin cancer that develops from melanocyte pigment cells.',
        whenToSeeDoctor: 'Dermatologists recommend professional evaluation for any mole following the ABCDE signs: Asymmetry, irregular Borders, varying Color, Diameter over 6mm, or any Evolving size, shape, or symptom.'
    },

    'Nail Fungus and other Nail Disease': {
        // TODO: Verify summary against DermNet NZ or AAD (Onychomycosis and nail disorders).
        title: 'Onychomycosis & Nail Diseases',
        whatItIs: 'Fungal dermatophyte infections or structural nail bed disorders that cause thickening, brittleness, yellow or brownish discoloration, or crumbling of the nails.',
        whenToSeeDoctor: 'Consult a doctor if thickened nails cause discomfort or pressure, if nail beds become inflamed, or if you have underlying diabetes or impaired peripheral circulation.'
    },

    'Poison Ivy Photos and other Contact Dermatitis': {
        // TODO: Verify summary against DermNet NZ or AAD (Allergic contact dermatitis & irritant dermatitis).
        title: 'Contact Dermatitis & Poison Ivy',
        whatItIs: 'An localized inflammatory skin response triggered by direct contact with an allergic trigger (such as plant oils, nickel, fragrances) or a harsh irritant chemical.',
        whenToSeeDoctor: 'Seek medical care if the reaction is widespread, involves the face or delicate areas, or fails to settle after several days of home soothing care.'
    },

    'Psoriasis pictures Lichen Planus and related diseases': {
        // TODO: Verify summary against DermNet NZ or AAD (Psoriasis & lichenoid dermatoses).
        title: 'Psoriasis & Lichen Planus',
        whatItIs: 'Chronic immune-mediated conditions typically marked by well-defined red plaques covered with silvery scales (psoriasis), or itchy, flat-topped violaceous papules (lichen planus).',
        whenToSeeDoctor: 'A dermatologist can provide an accurate diagnosis, recommend personalized topical or systemic treatment plans, and evaluate any associated joint stiffness.'
    },

    'Scabies Lyme Disease and other Infestations and Bites': {
        // TODO: Verify summary against DermNet NZ or AAD (Scabies, tick bites, and Lyme borreliosis).
        title: 'Scabies, Bites & Infestations',
        whatItIs: 'Skin reactions caused by microscopic mites (scabies), tick bites (including the expanding circular erythema migrans seen in Lyme disease), or other insect bites.',
        whenToSeeDoctor: 'Medical evaluation is essential for intense nighttime itching, after an embedded tick bite, or if you notice an expanding circular bullseye rash or flu-like symptoms.'
    },

    'Seborrheic Keratoses and other Benign Tumors': {
        // TODO: Verify summary against DermNet NZ or AAD (Seborrheic keratosis and benign lesions).
        title: 'Seborrheic Keratoses & Benign Tumors',
        whatItIs: 'Very common, harmless, non-cancerous growths that often have a waxy, raised, or "pasted-on" appearance, usually increasing in frequency with age.',
        whenToSeeDoctor: 'While benign seborrheic keratoses are harmless, having any new, dark, or changing growth assessed by a doctor ensures it is accurately distinguished from other pigmented lesions.'
    },

    'Systemic Disease': {
        // TODO: Verify summary against DermNet NZ or AAD (Cutaneous signs of systemic disease).
        title: 'Cutaneous Signs of Systemic Disease',
        whatItIs: 'Dermatological patterns and skin manifestations that may reflect underlying internal organ conditions, metabolic imbalances, or nutritional deficiencies.',
        whenToSeeDoctor: 'Consult a physician for a holistic health evaluation if cutaneous changes occur alongside unexplained weight changes, chronic tiredness, or changes in general wellness.'
    },

    'Tinea Ringworm Candidiasis and other Fungal Infections': {
        // TODO: Verify summary against DermNet NZ or AAD (Tinea infections & candidiasis).
        title: 'Tinea, Ringworm & Fungal Infections',
        whatItIs: 'Superficial fungal infections caused by dermatophytes or yeasts, often presenting as ring-shaped itchy scaly patches with clearing centers (ringworm) or red irritated skin folds.',
        whenToSeeDoctor: 'Visit a doctor or pharmacist if over-the-counter topical antifungal creams do not clear the condition after two weeks, or if it spreads to large surface areas.'
    },

    'Urticaria Hives': {
        // TODO: Verify summary against DermNet NZ or AAD (Urticaria / hives clinical guidelines).
        title: 'Urticaria (Hives & Wheals)',
        whatItIs: 'Sudden, transient, raised welts or wheals that are characteristically intensely itchy and often change location or fade within 24 hours.',
        whenToSeeDoctor: 'Seek emergency medical care immediately if hives are accompanied by lip or throat swelling, dizziness, or difficulty breathing. Consult a doctor if episodes recur over several weeks.'
    },

    'Vascular Tumors': {
        // TODO: Verify summary against DermNet NZ or AAD (Vascular lesions and hemangiomas).
        title: 'Vascular Tumors & Hemangiomas',
        whatItIs: 'Benign lesions composed of blood vessels, commonly appearing as bright red dots (cherry angiomas) or larger purplish vascular malformations.',
        whenToSeeDoctor: 'Have a doctor inspect vascular lesions that bleed repeatedly, ulcerate, grow rapidly, or cause physical irritation due to their location.'
    },

    'Vasculitis Photos': {
        // TODO: Verify summary against DermNet NZ or AAD (Cutaneous vasculitis).
        title: 'Vasculitis & Vascular Inflammation',
        whatItIs: 'Inflammatory changes in the blood vessel walls within the skin, which can produce non-blanching reddish-purple spots (palpable purpura) or localized ulcers.',
        whenToSeeDoctor: 'Any new, unexplained reddish-purple spots that do not fade when pressed firmly should be evaluated promptly by a medical professional.'
    },

    'Warts Molluscum and other Viral Infections': {
        // TODO: Verify summary against DermNet NZ or AAD (Viral warts and molluscum contagiosum).
        title: 'Warts, Molluscum & Viral Infections',
        whatItIs: 'Common viral infections of the skin outer layer, typically resulting in rough verrucous bumps (warts) or small dome-shaped papules with a central dimple (molluscum).',
        whenToSeeDoctor: 'Consult a healthcare provider if lesions cause pain, multiply rapidly, bleed, or occur on delicate areas such as the face or eyelids.'
    }
};

// Clean default fallback for unexpected or missing category keys
const SKIN_CLINICAL_INSIGHTS_DEFAULT = {
    title: 'General Dermatological Assessment',
    whatItIs: 'Dermatological pattern analysis compares visual features of skin images against reference clinical dataset categories.',
    whenToSeeDoctor: 'Any persistent, changing, painful, or unexplained skin rash or lesion should be examined in person by a qualified healthcare professional or board-certified dermatologist.'
};

// Helper function to safely retrieve clinical insight
function getSkinClinicalInsight(rawCategory) {
    if (!rawCategory) return SKIN_CLINICAL_INSIGHTS_DEFAULT;
    return SKIN_CLINICAL_INSIGHTS[rawCategory] || SKIN_CLINICAL_INSIGHTS_DEFAULT;
}

// Make accessible on window for browser scripts
if (typeof window !== 'undefined') {
    window.SKIN_CLINICAL_INSIGHTS = SKIN_CLINICAL_INSIGHTS;
    window.getSkinClinicalInsight = getSkinClinicalInsight;
}

// Export for Node/CommonJS environments if required
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { SKIN_CLINICAL_INSIGHTS, getSkinClinicalInsight };
}
