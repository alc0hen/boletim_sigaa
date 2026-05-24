import json
def get_demo_data():
    """
    Generator that yields demo data messages similar to the real SIGAA stream.
    Now yields raw-like grade structures for the backend calculator.
    """
    yield {
        "type": "user_info",
        "name": "Aluno Demonstração",
        "is_supporter": True
    }
    c1_id = 1
    yield {
        "type": "course_start",
        "id": c1_id,
        "name": "Matemática Aplicada",
        "obs": "Técnico em Informática"
    }
    yield {
        "type": "course_data",
        "id": c1_id,
        "data": [
            {'name': 'Unidade 1', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 10.0}]},
            {'name': 'Unidade 2', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 9.5}, {'name': 'Nota', 'value': 10.0}]},
            {'name': 'Unidade 3', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 10.0}]},
            {'name': 'Unidade 4', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 9.0}]}
        ]
    }
    yield {
        "type": "course_frequency",
        "id": c1_id,
        "data": {
            "total_faltas": 10,
            "max_faltas": 20,
            "percent": 12.5,
            "presencas": 40,
            "ausencias": 10,
            "nao_registradas": 10,
            "aulas_ministradas": 60,
            "aulas_total": 80,
            "aulas_per_session": 5,
            "logs": [
                {"date": "10/03/2026", "status": "Presente", "value": 5},
                {"date": "17/03/2026", "status": "Presente", "value": 5},
                {"date": "24/03/2026", "status": "Ausente", "value": 5},
                {"date": "31/03/2026", "status": "Presente", "value": 5},
                {"date": "07/04/2026", "status": "Presente", "value": 5},
                {"date": "14/04/2026", "status": "Presente", "value": 5},
                {"date": "21/04/2026", "status": "Presente", "value": 5},
                {"date": "28/04/2026", "status": "Ausente", "value": 5},
                {"date": "05/05/2026", "status": "Presente", "value": 5},
                {"date": "12/05/2026", "status": "Presente", "value": 5},
                {"date": "19/05/2026", "status": "Pendente", "value": 5},
                {"date": "26/05/2026", "status": "Pendente", "value": 5}
            ]
        }
    }
    c2_id = 2
    yield {
        "type": "course_start",
        "id": c2_id,
        "name": "Física I",
        "obs": "Técnico em Informática"
    }
    yield {
        "type": "course_data",
        "id": c2_id,
        "data": [
            {'name': 'Unidade 1', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 4.0}, {'name': 'Nota', 'value': 3.5}]},
            {'name': 'Unidade 2', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 5.0}]},
            {'name': 'Unidade 3', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 6.0}, {'name': 'Nota', 'value': 5.5}]},
            {'name': 'Unidade 4', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 4.0}]},
            {'name': 'R1', 'value': 7.5, 'type': 'single'}
        ]
    }
    yield {
        "type": "course_frequency",
        "id": c2_id,
        "data": {
            "total_faltas": 12,
            "max_faltas": 20,
            "percent": 15.0,
            "presencas": 60,
            "ausencias": 12,
            "nao_registradas": 0,
            "aulas_ministradas": 72,
            "aulas_total": 80,
            "aulas_per_session": 4,
            "logs": [
                {"date": "09/03/2026", "status": "Presente", "value": 4},
                {"date": "12/03/2026", "status": "Presente", "value": 4},
                {"date": "16/03/2026", "status": "Presente", "value": 4},
                {"date": "19/03/2026", "status": "Ausente", "value": 4},
                {"date": "23/03/2026", "status": "Presente", "value": 4},
                {"date": "26/03/2026", "status": "Presente", "value": 4},
                {"date": "30/03/2026", "status": "Presente", "value": 4},
                {"date": "02/04/2026", "status": "Presente", "value": 4},
                {"date": "06/04/2026", "status": "Ausente", "value": 4},
                {"date": "09/04/2026", "status": "Presente", "value": 4},
                {"date": "13/04/2026", "status": "Presente", "value": 4},
                {"date": "16/04/2026", "status": "Presente", "value": 4},
                {"date": "20/04/2026", "status": "Presente", "value": 4},
                {"date": "23/04/2026", "status": "Presente", "value": 4},
                {"date": "27/04/2026", "status": "Presente", "value": 4},
                {"date": "30/04/2026", "status": "Presente", "value": 4},
                {"date": "04/05/2026", "status": "Presente", "value": 4},
                {"date": "07/05/2026", "status": "Ausente", "value": 4}
            ]
        }
    }
    c3_id = 3
    yield {
        "type": "course_start",
        "id": c3_id,
        "name": "Programação Web",
        "obs": "Técnico em Informática"
    }
    yield {
        "type": "course_data",
        "id": c3_id,
        "data": [
            {'name': 'Unidade 1', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 8.0}]},
            {'name': 'Unidade 2', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 7.5}]},
            {'name': 'Unidade 3', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 8.0}]},
            {'name': 'Unidade 4', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 9.0}]}
        ]
    }
    yield {
        "type": "course_frequency",
        "id": c3_id,
        "data": {
            "total_faltas": 25,
            "max_faltas": 20,
            "percent": 31.2,
            "presencas": 20,
            "ausencias": 25,
            "nao_registradas": 15,
            "aulas_ministradas": 60,
            "aulas_total": 80,
            "aulas_per_session": 5,
            "logs": [
                {"date": "11/03/2026", "status": "Presente", "value": 5},
                {"date": "18/03/2026", "status": "Ausente", "value": 5},
                {"date": "25/03/2026", "status": "Ausente", "value": 5},
                {"date": "01/04/2026", "status": "Presente", "value": 5},
                {"date": "08/04/2026", "status": "Ausente", "value": 5},
                {"date": "15/04/2026", "status": "Presente", "value": 5},
                {"date": "22/04/2026", "status": "Ausente", "value": 5},
                {"date": "29/04/2026", "status": "Ausente", "value": 5},
                {"date": "06/05/2026", "status": "Presente", "value": 5},
                {"date": "13/05/2026", "status": "Pendente", "value": 5},
                {"date": "20/05/2026", "status": "Pendente", "value": 5},
                {"date": "27/05/2026", "status": "Pendente", "value": 5}
            ]
        }
    }
    c4_id = 4
    yield {
        "type": "course_start",
        "id": c4_id,
        "name": "Língua Portuguesa",
        "obs": "Técnico em Informática"
    }
    yield {
        "type": "course_data",
        "id": c4_id,
        "data": [
            {'name': 'Unidade 1', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 7.0}]},
            {'name': 'Unidade 2', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 6.5}]},
            {'name': 'Unidade 3', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 8.0}]},
            {'name': 'Unidade 4', 'type': 'group', 'grades': []}
        ]
    }
    yield {
        "type": "course_frequency",
        "id": c4_id,
        "data": {
            "total_faltas": 8,
            "max_faltas": 20,
            "percent": 10.0,
            "presencas": 40,
            "ausencias": 8,
            "nao_registradas": 8,
            "aulas_ministradas": 56,
            "aulas_total": 80,
            "aulas_per_session": 4,
            "logs": [
                {"date": "13/03/2026", "status": "Presente", "value": 4},
                {"date": "20/03/2026", "status": "Presente", "value": 4},
                {"date": "27/03/2026", "status": "Ausente", "value": 4},
                {"date": "03/04/2026", "status": "Presente", "value": 4},
                {"date": "10/04/2026", "status": "Presente", "value": 4},
                {"date": "17/04/2026", "status": "Presente", "value": 4},
                {"date": "24/04/2026", "status": "Presente", "value": 4},
                {"date": "01/05/2026", "status": "Ausente", "value": 4},
                {"date": "08/05/2026", "status": "Presente", "value": 4},
                {"date": "15/05/2026", "status": "Presente", "value": 4},
                {"date": "22/05/2026", "status": "Presente", "value": 4},
                {"date": "29/05/2026", "status": "Presente", "value": 4},
                {"date": "05/06/2026", "status": "Pendente", "value": 4},
                {"date": "12/06/2026", "status": "Pendente", "value": 4}
            ]
        }
    }
