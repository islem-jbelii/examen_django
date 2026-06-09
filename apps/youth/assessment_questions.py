"""
youth/assessment_questions.py
10 predefined interest/aptitude questions used in InterestAssessmentView.
Each question maps to one or more CareerSector names via SECTOR_WEIGHTS.
"""

QUESTIONS = [
    {
        "id": "q1",
        "text": "Aimez-vous résoudre des problèmes techniques ou travailler avec des ordinateurs ?",
        "choices": [
            ("1", "Pas du tout"),
            ("2", "Un peu"),
            ("3", "Assez"),
            ("4", "Beaucoup"),
            ("5", "Passionnément"),
        ],
        "sectors": ["Informatique"],
    },
    {
        "id": "q2",
        "text": "Êtes-vous attiré(e) par les métiers de la santé et du soin aux personnes ?",
        "choices": [
            ("1", "Pas du tout"),
            ("2", "Un peu"),
            ("3", "Assez"),
            ("4", "Beaucoup"),
            ("5", "Passionnément"),
        ],
        "sectors": ["Santé"],
    },
    {
        "id": "q3",
        "text": "Aimez-vous travailler en plein air, avec la nature ou les animaux ?",
        "choices": [
            ("1", "Pas du tout"),
            ("2", "Un peu"),
            ("3", "Assez"),
            ("4", "Beaucoup"),
            ("5", "Passionnément"),
        ],
        "sectors": ["Agriculture"],
    },
    {
        "id": "q4",
        "text": "Êtes-vous à l'aise avec les chiffres, la gestion et le commerce ?",
        "choices": [
            ("1", "Pas du tout"),
            ("2", "Un peu"),
            ("3", "Assez"),
            ("4", "Beaucoup"),
            ("5", "Passionnément"),
        ],
        "sectors": ["Commerce"],
    },
    {
        "id": "q5",
        "text": "Aimez-vous créer des objets avec vos mains ou pratiquer des métiers manuels ?",
        "choices": [
            ("1", "Pas du tout"),
            ("2", "Un peu"),
            ("3", "Assez"),
            ("4", "Beaucoup"),
            ("5", "Passionnément"),
        ],
        "sectors": ["Artisanat"],
    },
    {
        "id": "q6",
        "text": "Êtes-vous intéressé(e) par l'accueil, le tourisme et la découverte culturelle ?",
        "choices": [
            ("1", "Pas du tout"),
            ("2", "Un peu"),
            ("3", "Assez"),
            ("4", "Beaucoup"),
            ("5", "Passionnément"),
        ],
        "sectors": ["Tourisme"],
    },
    {
        "id": "q7",
        "text": "Aimez-vous concevoir, construire ou comprendre le fonctionnement des machines ?",
        "choices": [
            ("1", "Pas du tout"),
            ("2", "Un peu"),
            ("3", "Assez"),
            ("4", "Beaucoup"),
            ("5", "Passionnément"),
        ],
        "sectors": ["Ingénierie"],
    },
    {
        "id": "q8",
        "text": "Aimez-vous enseigner, expliquer ou aider les autres à apprendre ?",
        "choices": [
            ("1", "Pas du tout"),
            ("2", "Un peu"),
            ("3", "Assez"),
            ("4", "Beaucoup"),
            ("5", "Passionnément"),
        ],
        "sectors": ["Éducation"],
    },
    {
        "id": "q9",
        "text": "Préférez-vous travailler en équipe plutôt que seul(e) ?",
        "choices": [
            ("1", "Toujours seul(e)"),
            ("2", "Plutôt seul(e)"),
            ("3", "Indifférent(e)"),
            ("4", "Plutôt en équipe"),
            ("5", "Toujours en équipe"),
        ],
        "sectors": ["Commerce", "Tourisme", "Éducation"],
    },
    {
        "id": "q10",
        "text": "Êtes-vous prêt(e) à suivre une formation longue (3 ans ou plus) pour votre métier ?",
        "choices": [
            ("1", "Non, je veux travailler rapidement"),
            ("2", "Peut-être 1-2 ans"),
            ("3", "Oui, 2-3 ans"),
            ("4", "Oui, 3-5 ans"),
            ("5", "Oui, autant qu'il faut"),
        ],
        "sectors": ["Santé", "Ingénierie", "Informatique"],
    },
]


def compute_sector_scores(responses: dict) -> dict:
    """
    Given a dict of {question_id: answer_value (str "1"-"5")},
    return a dict of {sector_name: total_score}.
    """
    sector_scores = {}
    for question in QUESTIONS:
        answer = responses.get(question["id"])
        if answer is None:
            continue
        try:
            value = int(answer)
        except (ValueError, TypeError):
            continue
        for sector_name in question["sectors"]:
            sector_scores[sector_name] = sector_scores.get(sector_name, 0) + value
    return sector_scores


def get_recommended_sectors(responses: dict, top_n: int = 3):
    """
    Return the top N sector names sorted by score descending.
    Only include sectors with score >= 8 (threshold for genuine interest).
    """
    scores = compute_sector_scores(responses)
    sorted_sectors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [name for name, score in sorted_sectors[:top_n] if score >= 8]
