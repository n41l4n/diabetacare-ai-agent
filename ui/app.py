import json
import uuid
import requests
import streamlit as st


# =========================================================
# Page Configuration
# =========================================================

st.set_page_config(
    page_title="DiabetaCare AI",
    page_icon="🩺",
    layout="wide"
)


# =========================================================
# API Configuration
# =========================================================

LANGFLOW_URL = "http://localhost:7860/api/v1/run/d858ccf4-119a-4193-9a85-3a2cc92a0a39"
FASTAPI_PREDICT_URL = "http://127.0.0.1:8000/predict"


# =========================================================
# Helper: Extract text from LangFlow response
# =========================================================

def extract_text_from_langflow_response(data):
    possible_paths = [
        ["outputs", 0, "outputs", 0, "results", "message", "text"],
        ["outputs", 0, "outputs", 0, "results", "text"],
        ["outputs", 0, "outputs", 0, "artifacts", "message"],
        ["outputs", 0, "outputs", 0, "artifacts", "text"],
    ]

    for path in possible_paths:
        try:
            value = data
            for key in path:
                value = value[key]

            if isinstance(value, str) and value.strip():
                return value

        except Exception:
            pass

    def find_text(obj):
        if isinstance(obj, dict):
            for key in ["text", "message", "content"]:
                if key in obj and isinstance(obj[key], str) and len(obj[key]) > 30:
                    return obj[key]

            for value in obj.values():
                result = find_text(value)
                if result:
                    return result

        elif isinstance(obj, list):
            for item in obj:
                result = find_text(item)
                if result:
                    return result

        return None

    found = find_text(data)

    if found:
        return found

    return json.dumps(data, indent=2, ensure_ascii=False)


# =========================================================
# Helper: Run LangFlow
# =========================================================

def call_agentic_flow(agent_message):
    """
    Mengirim pesan ke LangFlow Agentic Flow.

    Agentic Flow memiliki tools seperti:
    - Diabetes Prediction Tool
    - Form Term Explainer Tool
    - Red Flag Safety Tool
    - What-if Simulator Tool
    """

    api_key = st.secrets["LANGFLOW_API_KEY"]

    payload = {
        "output_type": "chat",
        "input_type": "chat",
        "input_value": agent_message,
        "session_id": str(uuid.uuid4())
    }

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    response = requests.post(
        LANGFLOW_URL,
        json=payload,
        headers=headers,
        timeout=120
    )

    response.raise_for_status()
    return response.json()


def run_langflow(user_payload):
    """
    Menjalankan screening utama melalui Agentic Flow.
    Streamlit tidak langsung mengirim JSON mentah, tetapi memberi instruksi
    agar Agent menggunakan Diabetes Prediction Tool.
    """

    agent_message = f"""
User mengisi form screening risiko diabetes.

Tugas Anda:
1. Gunakan Diabetes Prediction Tool untuk memproses data kesehatan berikut.
2. Jelaskan hasilnya sebagai estimasi risiko awal, bukan diagnosis.
3. Jelaskan faktor yang berkontribusi.
4. Berikan edukasi dan saran umum yang aman.
5. Sertakan disclaimer medis.

Data kesehatan JSON:
{json.dumps(user_payload, ensure_ascii=False, indent=2)}
"""

    return call_agentic_flow(agent_message)


def run_agent_help_chat(user_question):
    """
    Menjalankan help chat melalui Agentic Flow.
    Agent akan memilih Form Term Explainer Tool atau Red Flag Safety Tool.
    """

    agent_message = f"""
User bertanya tentang istilah, fitur, atau keamanan pada aplikasi DiabetaCare AI.

Tugas Anda:
1. Jika pertanyaan berkaitan dengan BMI, HighBP, HighChol, GenHlth, MentHlth, PhysHlth, Age, Sex, atau What-if Simulator, gunakan Form Term Explainer Tool.
2. Jika user menyebut gejala seperti sering haus, sering buang air kecil, berat badan turun tanpa sebab, luka sulit sembuh, pandangan kabur, atau lemas berat, gunakan Red Flag Safety Tool.
3. Jawab dengan bahasa Indonesia yang sederhana, singkat, dan ramah.
4. Jangan memberikan diagnosis medis.
5. Jika relevan, ingatkan bahwa aplikasi ini hanya untuk edukasi dan screening awal.

Pertanyaan user:
{user_question}
"""

    return extract_text_from_langflow_response(call_agentic_flow(agent_message))


def run_agent_what_if(current_payload, scenario_payload):
    """
    Menjalankan narasi What-if melalui Agentic Flow.
    Agent akan menggunakan What-if Simulator Tool.
    """

    what_if_payload = {
        "current": current_payload,
        "scenario": scenario_payload
    }

    agent_message = f"""
User ingin menjalankan What-if Risk Simulator.

Tugas Anda:
1. Gunakan What-if Simulator Tool untuk membandingkan data current dan scenario.
2. Jelaskan perubahan risk level dan probability secara sederhana.
3. Jelaskan faktor perubahan yang paling mungkin berpengaruh.
4. Tegaskan bahwa simulasi ini bersifat edukatif dan bukan kepastian medis.

Data current dan scenario:
{json.dumps(what_if_payload, ensure_ascii=False, indent=2)}
"""

    return extract_text_from_langflow_response(call_agentic_flow(agent_message))


# =========================================================
# Helper: Run FastAPI Prediction Directly
# Used for What-if Simulator
# =========================================================

def run_prediction_api(user_payload):
    response = requests.post(
        FASTAPI_PREDICT_URL,
        json=user_payload,
        timeout=60
    )

    response.raise_for_status()
    return response.json()


# =========================================================
# Helper: BMI
# =========================================================

def calculate_bmi(weight_kg, height_cm):
    height_m = height_cm / 100

    if height_m <= 0:
        return 0

    return round(weight_kg / (height_m ** 2), 1)


def get_bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal"
    elif bmi < 30:
        return "Overweight"
    else:
        return "Obesity"


# =========================================================
# Helper: Scenario Mapping
# =========================================================

def scenario_binary_value(choice, current_value):
    if choice == "Ikuti data utama":
        return current_value
    if choice == "Ya":
        return 1
    return 0


def probability_to_percent(probability):
    return round(float(probability) * 100, 1)


# =========================================================
# Helper: Wellness Plan
# =========================================================

def generate_7_day_plan(user_payload, prediction_result):
    risk_level = prediction_result.get("risk_level", "Unknown")

    plan = []

    plan.append(
        ("Hari 1", "Catat kondisi awal: berat badan, aktivitas harian, pola makan, dan keluhan umum yang dirasakan.")
    )

    if user_payload.get("PhysActivity") == 0:
        plan.append(
            ("Hari 2", "Mulai aktivitas fisik ringan, misalnya jalan kaki 10–15 menit sesuai kemampuan tubuh.")
        )
    else:
        plan.append(
            ("Hari 2", "Pertahankan aktivitas fisik rutin dan catat durasi aktivitas harian.")
        )

    if user_payload.get("Fruits") == 0 or user_payload.get("Veggies") == 0:
        plan.append(
            ("Hari 3", "Tambahkan buah atau sayur ke salah satu porsi makan harian.")
        )
    else:
        plan.append(
            ("Hari 3", "Pertahankan konsumsi buah dan sayur, serta perhatikan porsi makanan seimbang.")
        )

    if user_payload.get("BMI", 0) >= 25:
        plan.append(
            ("Hari 4", "Perhatikan pola makan dan porsi makan. Fokus pada langkah kecil untuk menjaga berat badan lebih sehat.")
        )
    else:
        plan.append(
            ("Hari 4", "Pertahankan berat badan sehat dengan pola makan seimbang dan aktivitas fisik.")
        )

    if user_payload.get("Smoker") == 1:
        plan.append(
            ("Hari 5", "Kurangi paparan rokok dan pertimbangkan mencari dukungan profesional jika ingin berhenti merokok.")
        )
    else:
        plan.append(
            ("Hari 5", "Pertahankan kebiasaan tidak merokok dan hindari paparan asap rokok.")
        )

    if user_payload.get("HighBP") == 1 or user_payload.get("HighChol") == 1:
        plan.append(
            ("Hari 6", "Jika memungkinkan, pantau tekanan darah atau kolesterol secara berkala dan simpan catatannya.")
        )
    else:
        plan.append(
            ("Hari 6", "Lakukan pemeriksaan kesehatan berkala sebagai langkah pencegahan.")
        )

    if risk_level in ["Moderate", "High"]:
        plan.append(
            ("Hari 7", "Pertimbangkan berkonsultasi dengan tenaga kesehatan untuk memahami risiko dan pemeriksaan lanjutan yang sesuai.")
        )
    else:
        plan.append(
            ("Hari 7", "Evaluasi kebiasaan selama seminggu dan pilih satu kebiasaan sehat yang ingin dipertahankan.")
        )

    markdown = "### 🗓️ Personalized 7-Day Wellness Plan\n\n"
    markdown += "Rencana ini bersifat edukatif umum, bukan instruksi medis personal.\n\n"
    markdown += "| Hari | Rekomendasi Umum |\n"
    markdown += "|---|---|\n"

    for day, recommendation in plan:
        markdown += f"| {day} | {recommendation} |\n"

    return markdown


# =========================================================
# Help Chat Logic
# =========================================================

FIELD_EXPLANATIONS = {
    "bmi": (
        "BMI atau Body Mass Index adalah ukuran perbandingan antara berat badan dan tinggi badan. "
        "Di aplikasi ini, BMI dihitung otomatis dari berat badan dan tinggi badan yang kamu isi."
    ),
    "highbp": (
        "HighBP berarti apakah seseorang memiliki tekanan darah tinggi. "
        "Pilih 'Ya' jika kamu pernah diberitahu oleh dokter atau tenaga kesehatan bahwa tekanan darah kamu tinggi."
    ),
    "highchol": (
        "HighChol berarti apakah seseorang memiliki kolesterol tinggi. "
        "Pilih 'Ya' jika kamu pernah diberitahu bahwa kadar kolesterol kamu tinggi."
    ),
    "smoker": (
        "Smoker berarti apakah seseorang pernah merokok. "
        "Di dataset ini, status merokok digunakan sebagai salah satu indikator gaya hidup."
    ),
    "physactivity": (
        "PhysActivity berarti apakah kamu melakukan aktivitas fisik. "
        "Contohnya jalan kaki, olahraga ringan, bersepeda, atau aktivitas fisik lain."
    ),
    "fruits": (
        "Fruits berarti apakah kamu relatif rutin mengonsumsi buah. "
        "Pilih 'Ya' jika kamu cukup sering mengonsumsi buah dalam pola makan sehari-hari."
    ),
    "veggies": (
        "Veggies berarti apakah kamu relatif rutin mengonsumsi sayur. "
        "Pilih 'Ya' jika kamu cukup sering mengonsumsi sayur dalam pola makan sehari-hari."
    ),
    "genhlth": (
        "GenHlth adalah penilaian kondisi kesehatan umum menurut diri sendiri. "
        "Nilai 1 berarti sangat baik, sedangkan nilai 5 berarti kurang baik."
    ),
    "menthlth": (
        "MentHlth adalah jumlah hari dalam 30 hari terakhir ketika kondisi mental terasa kurang baik, "
        "misalnya stres, cemas, atau mood buruk."
    ),
    "physhlth": (
        "PhysHlth adalah jumlah hari dalam 30 hari terakhir ketika kondisi fisik terasa kurang baik, "
        "misalnya sakit, tidak fit, atau kelelahan berat."
    ),
    "age": (
        "Age pada dataset ini berbentuk kategori usia, bukan angka umur langsung. "
        "Di UI ini kategori sudah diterjemahkan menjadi rentang usia seperti 18–24, 25–29, dan seterusnya."
    ),
    "sex": (
        "Sex adalah jenis kelamin sesuai format dataset. "
        "Di aplikasi ini pilihannya sudah dibuat menjadi Perempuan atau Laki-laki."
    ),
    "whatif": (
        "What-if Simulator adalah fitur untuk melihat simulasi perubahan estimasi risiko jika beberapa faktor gaya hidup diubah, "
        "misalnya target berat badan, aktivitas fisik, konsumsi buah/sayur, atau status merokok."
    ),
    "disclaimer": (
        "Aplikasi ini hanya untuk screening awal dan edukasi. "
        "Hasilnya bukan diagnosis medis dan tidak menggantikan konsultasi dengan dokter atau tenaga kesehatan."
    )
}


def help_chat_response(question):
    q = question.lower()

    if "bmi" in q or "berat" in q or "tinggi" in q:
        return FIELD_EXPLANATIONS["bmi"]

    if "tekanan" in q or "darah" in q or "highbp" in q:
        return FIELD_EXPLANATIONS["highbp"]

    if "kolesterol" in q or "highchol" in q:
        return FIELD_EXPLANATIONS["highchol"]

    if "rokok" in q or "merokok" in q or "smoker" in q:
        return FIELD_EXPLANATIONS["smoker"]

    if "aktivitas" in q or "olahraga" in q or "physactivity" in q:
        return FIELD_EXPLANATIONS["physactivity"]

    if "buah" in q or "fruits" in q:
        return FIELD_EXPLANATIONS["fruits"]

    if "sayur" in q or "veggies" in q:
        return FIELD_EXPLANATIONS["veggies"]

    if "genhlth" in q or "kesehatan umum" in q or "kondisi kesehatan" in q:
        return FIELD_EXPLANATIONS["genhlth"]

    if "mental" in q or "menthlth" in q:
        return FIELD_EXPLANATIONS["menthlth"]

    if "fisik" in q or "physhlth" in q:
        return FIELD_EXPLANATIONS["physhlth"]

    if "umur" in q or "usia" in q or "age" in q:
        return FIELD_EXPLANATIONS["age"]

    if "sex" in q or "jenis kelamin" in q or "gender" in q:
        return FIELD_EXPLANATIONS["sex"]

    if "what" in q or "simulasi" in q or "skenario" in q:
        return FIELD_EXPLANATIONS["whatif"]

    if "diagnosis" in q or "dokter" in q or "medis" in q:
        return FIELD_EXPLANATIONS["disclaimer"]

    return (
        "Saya bisa membantu menjelaskan istilah di form, seperti BMI, tekanan darah tinggi, "
        "kolesterol tinggi, aktivitas fisik, GenHlth, MentHlth, PhysHlth, Age, Sex, dan What-if Simulator. "
        "Contoh pertanyaan: 'BMI itu apa?', 'GenHlth isi apa?', atau 'What-if Simulator itu apa?'"
    )


# =========================================================
# Sidebar Help Chat
# =========================================================

with st.sidebar:
    st.header("💬 Tanya Istilah Form")

    st.write(
        "Bingung dengan istilah seperti BMI, tekanan darah tinggi, GenHlth, PhysHlth, atau What-if Simulator? "
        "Tanyakan di sini sebelum mengisi form."
    )

    if "help_messages" not in st.session_state:
        st.session_state.help_messages = [
            {
                "role": "assistant",
                "content": "Halo! Saya bisa bantu jelaskan istilah di form. Contoh: BMI itu apa?"
            }
        ]

    if st.button("🔄 Reset Chat Bantuan"):
        st.session_state.help_messages = [
            {
                "role": "assistant",
                "content": "Halo! Saya bisa bantu jelaskan istilah di form. Contoh: BMI itu apa?"
            }
        ]
        st.rerun()

    st.divider()

    for message in st.session_state.help_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    with st.form("help_chat_form", clear_on_submit=True):
        user_question = st.text_input(
            "Tulis pertanyaan",
            placeholder="Contoh: BMI itu apa?"
        )

        ask_button = st.form_submit_button("Tanya")

    if ask_button and user_question.strip():
        st.session_state.help_messages.append(
            {
                "role": "user",
                "content": user_question
            }
        )

        try:
            answer = run_agent_help_chat(user_question)
        except Exception as e:
            # Fallback lokal agar help chat tetap berjalan jika Agentic Flow sedang tidak aktif.
            answer = (
                help_chat_response(user_question)
                + f"\n\n_Catatan teknis: Agentic Help Chat sedang tidak dapat dihubungi ({e}). Jawaban ini memakai fallback lokal._"
            )

        st.session_state.help_messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        st.rerun()

    st.divider()

    st.caption(
        "Help chat ini dikirim ke LangFlow Agentic Flow. "
        "Agent dapat memilih Form Term Explainer Tool atau Red Flag Safety Tool."
    )


# =========================================================
# Main Header
# =========================================================

st.title("🩺 DiabetaCare AI")
st.subheader("Diabetes Risk Screening, Education, and What-if Simulator")

st.write(
    "Aplikasi ini membantu melakukan **screening awal risiko diabetes** berdasarkan indikator kesehatan sederhana. "
    "Sistem menggunakan **LangFlow Agentic Flow** yang dapat memilih tools seperti Diabetes Prediction Tool, "
    "Form Term Explainer Tool, Red Flag Safety Tool, dan What-if Simulator Tool."
)

st.warning(
    "Disclaimer: Hasil aplikasi ini bukan diagnosis medis dan tidak boleh digunakan sebagai pengganti konsultasi dengan dokter atau tenaga kesehatan profesional."
)

st.divider()


# =========================================================
# Main Tabs
# =========================================================

screening_tab, about_tab = st.tabs(
    [
        "🩺 Screening & Simulator",
        "ℹ️ Tentang Aplikasi"
    ]
)


# =========================================================
# Screening Tab
# =========================================================

with screening_tab:
    form_col, simulator_col = st.columns([1.15, 0.85])

    with form_col:
        st.subheader("Form Screening Risiko Diabetes")

        with st.form("diabetes_form"):
            st.markdown("### 1. Kondisi kesehatan dasar")

            col1, col2 = st.columns(2)

            with col1:
                HighBP = st.selectbox(
                    "Apakah memiliki tekanan darah tinggi?",
                    options=[0, 1],
                    format_func=lambda x: "Ya" if x == 1 else "Tidak",
                    help="Pilih Ya jika pernah diberitahu tenaga kesehatan bahwa tekanan darah kamu tinggi."
                )

                HighChol = st.selectbox(
                    "Apakah memiliki kolesterol tinggi?",
                    options=[0, 1],
                    format_func=lambda x: "Ya" if x == 1 else "Tidak",
                    help="Pilih Ya jika pernah diberitahu bahwa kadar kolesterol kamu tinggi."
                )

            with col2:
                GenHlth = st.selectbox(
                    "Kondisi kesehatan umum",
                    options=[1, 2, 3, 4, 5],
                    format_func=lambda x: {
                        1: "Excellent / Sangat baik",
                        2: "Very good / Baik sekali",
                        3: "Good / Baik",
                        4: "Fair / Cukup",
                        5: "Poor / Kurang baik"
                    }[x],
                    help="Penilaian umum tentang kesehatan diri sendiri."
                )

                Sex = st.selectbox(
                    "Jenis kelamin",
                    options=[0, 1],
                    format_func=lambda x: "Perempuan" if x == 0 else "Laki-laki"
                )

            st.markdown("### 2. Berat, tinggi, dan BMI")

            col3, col4 = st.columns(2)

            with col3:
                weight = st.number_input(
                    "Berat badan (kg)",
                    min_value=20.0,
                    max_value=250.0,
                    value=80.0,
                    step=0.5,
                    help="Masukkan berat badan dalam kilogram."
                )

            with col4:
                height = st.number_input(
                    "Tinggi badan (cm)",
                    min_value=100.0,
                    max_value=230.0,
                    value=165.0,
                    step=0.5,
                    help="Masukkan tinggi badan dalam centimeter."
                )

            BMI = calculate_bmi(weight, height)
            bmi_category = get_bmi_category(BMI)

            st.info(f"BMI otomatis: **{BMI}** — kategori: **{bmi_category}**")

            st.markdown("### 3. Gaya hidup")

            col5, col6 = st.columns(2)

            with col5:
                Smoker = st.selectbox(
                    "Pernah merokok?",
                    options=[0, 1],
                    format_func=lambda x: "Ya" if x == 1 else "Tidak"
                )

                PhysActivity = st.selectbox(
                    "Aktif secara fisik?",
                    options=[0, 1],
                    format_func=lambda x: "Ya" if x == 1 else "Tidak",
                    help="Contoh: jalan kaki, olahraga ringan, atau aktivitas fisik lain."
                )

            with col6:
                Fruits = st.selectbox(
                    "Rutin konsumsi buah?",
                    options=[0, 1],
                    format_func=lambda x: "Ya" if x == 1 else "Tidak"
                )

                Veggies = st.selectbox(
                    "Rutin konsumsi sayur?",
                    options=[0, 1],
                    format_func=lambda x: "Ya" if x == 1 else "Tidak"
                )

            st.markdown("### 4. Kondisi 30 hari terakhir dan usia")

            MentHlth = st.slider(
                "Jumlah hari kondisi mental kurang baik dalam 30 hari terakhir",
                min_value=0,
                max_value=30,
                value=5,
                help="Contoh: stres, cemas, atau mood buruk."
            )

            PhysHlth = st.slider(
                "Jumlah hari kondisi fisik kurang baik dalam 30 hari terakhir",
                min_value=0,
                max_value=30,
                value=10,
                help="Contoh: sakit, tidak fit, atau kelelahan berat."
            )

            Age = st.selectbox(
                "Kategori usia",
                options=list(range(1, 14)),
                index=8,
                format_func=lambda x: {
                    1: "18–24 tahun",
                    2: "25–29 tahun",
                    3: "30–34 tahun",
                    4: "35–39 tahun",
                    5: "40–44 tahun",
                    6: "45–49 tahun",
                    7: "50–54 tahun",
                    8: "55–59 tahun",
                    9: "60–64 tahun",
                    10: "65–69 tahun",
                    11: "70–74 tahun",
                    12: "75–79 tahun",
                    13: "80 tahun ke atas"
                }[x],
                help="Kategori usia mengikuti format dataset CDC Diabetes Health Indicators."
            )

            submitted = st.form_submit_button("🔍 Cek Risiko Diabetes")

    with simulator_col:
        st.subheader("🔄 What-if Risk Simulator")

        with st.container(border=True):
            st.caption(
                "Fitur ini membandingkan estimasi risiko saat ini dengan skenario perubahan gaya hidup sederhana."
            )

            enable_what_if = st.toggle(
                "Aktifkan simulasi perubahan gaya hidup",
                value=True
            )

            if enable_what_if:
                st.markdown("#### Skenario Simulasi")

                target_weight = st.number_input(
                    "Target berat badan untuk simulasi (kg)",
                    min_value=20.0,
                    max_value=250.0,
                    value=max(20.0, weight - 5),
                    step=0.5,
                    help="Masukkan target berat badan untuk melihat simulasi perubahan BMI."
                )

                scenario_bmi_preview = calculate_bmi(target_weight, height)

                st.info(
                    f"Estimasi BMI pada skenario ini: **{scenario_bmi_preview}** "
                    f"— kategori: **{get_bmi_category(scenario_bmi_preview)}**"
                )

                scenario_phys_activity_choice = st.selectbox(
                    "Skenario aktivitas fisik",
                    options=["Ikuti data utama", "Ya", "Tidak"],
                    index=1
                )

                scenario_fruits_choice = st.selectbox(
                    "Skenario konsumsi buah",
                    options=["Ikuti data utama", "Ya", "Tidak"],
                    index=1
                )

                scenario_veggies_choice = st.selectbox(
                    "Skenario konsumsi sayur",
                    options=["Ikuti data utama", "Ya", "Tidak"],
                    index=1
                )

                scenario_smoker_choice = st.selectbox(
                    "Skenario merokok",
                    options=["Ikuti data utama", "Ya", "Tidak"],
                    index=2
                )

                st.caption(
                    "Simulasi ini bersifat edukatif. Perubahan probabilitas bukan kepastian medis."
                )

            else:
                target_weight = weight
                scenario_phys_activity_choice = "Ikuti data utama"
                scenario_fruits_choice = "Ikuti data utama"
                scenario_veggies_choice = "Ikuti data utama"
                scenario_smoker_choice = "Ikuti data utama"

                st.info(
                    "What-if Simulator sedang dinonaktifkan. "
                    "Aktifkan fitur ini jika ingin membandingkan skenario perubahan gaya hidup."
                )

        with st.container(border=True):
            st.markdown("### 💬 Butuh bantuan isi form?")
            st.markdown(
                """
                Gunakan sidebar **Tanya Istilah Form** untuk bertanya arti istilah seperti:

                - BMI
                - GenHlth
                - MentHlth
                - PhysHlth
                - What-if Simulator
                """
            )

    # =====================================================
    # Submit Result Section
    # =====================================================

    if submitted:
        user_payload = {
            "HighBP": HighBP,
            "HighChol": HighChol,
            "BMI": BMI,
            "Smoker": Smoker,
            "PhysActivity": PhysActivity,
            "Fruits": Fruits,
            "Veggies": Veggies,
            "GenHlth": GenHlth,
            "MentHlth": MentHlth,
            "PhysHlth": PhysHlth,
            "Age": Age,
            "Sex": Sex
        }

        st.divider()

        st.markdown("## 📋 Hasil Screening")

        st.info(
            "Berikut adalah hasil estimasi risiko berdasarkan data yang kamu isi. "
            "Hasil ini hanya untuk screening awal dan bukan diagnosis medis."
        )

        with st.expander("Lihat data JSON yang dikirim ke LangFlow"):
            st.json(user_payload)

        current_prediction_for_plan = None

        with st.spinner("Mengirim data ke LangFlow dan membuat penjelasan..."):
            try:
                langflow_response = run_langflow(user_payload)
                answer = extract_text_from_langflow_response(langflow_response)

                st.success("Hasil screening berhasil dibuat")

                with st.container(border=True):
                    st.markdown(answer)

            except requests.exceptions.ConnectionError:
                st.error(
                    "Tidak bisa terhubung ke LangFlow. Pastikan LangFlow berjalan di http://localhost:7860."
                )

            except requests.exceptions.HTTPError as e:
                st.error(f"LangFlow mengembalikan HTTP error: {e}")

                try:
                    st.code(e.response.text)
                except Exception:
                    pass

            except KeyError:
                st.error(
                    "LANGFLOW_API_KEY belum ditemukan. Pastikan file .streamlit/secrets.toml sudah dibuat."
                )

            except Exception as e:
                st.error(f"Terjadi error saat menjalankan LangFlow: {e}")

        # =====================================================
        # What-if Risk Simulator Result
        # =====================================================

        if enable_what_if:
            st.divider()
            st.markdown("## 🔄 What-if Risk Simulator")

            scenario_bmi = calculate_bmi(target_weight, height)

            scenario_payload = user_payload.copy()
            scenario_payload["BMI"] = scenario_bmi
            scenario_payload["PhysActivity"] = scenario_binary_value(
                scenario_phys_activity_choice,
                user_payload["PhysActivity"]
            )
            scenario_payload["Fruits"] = scenario_binary_value(
                scenario_fruits_choice,
                user_payload["Fruits"]
            )
            scenario_payload["Veggies"] = scenario_binary_value(
                scenario_veggies_choice,
                user_payload["Veggies"]
            )
            scenario_payload["Smoker"] = scenario_binary_value(
                scenario_smoker_choice,
                user_payload["Smoker"]
            )

            with st.expander("Lihat JSON skenario simulasi"):
                st.json(scenario_payload)

            with st.spinner("Menjalankan simulasi risiko saat ini dan skenario perubahan..."):
                try:
                    current_prediction = run_prediction_api(user_payload)
                    scenario_prediction = run_prediction_api(scenario_payload)
                    current_prediction_for_plan = current_prediction

                    current_prob = probability_to_percent(
                        current_prediction.get("diabetes_probability", 0)
                    )
                    scenario_prob = probability_to_percent(
                        scenario_prediction.get("diabetes_probability", 0)
                    )
                    delta = round(scenario_prob - current_prob, 1)

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        st.metric(
                            "Risiko Saat Ini",
                            current_prediction.get("risk_level", "Unknown"),
                            f"{current_prob}%"
                        )

                    with col_b:
                        st.metric(
                            "Risiko Skenario",
                            scenario_prediction.get("risk_level", "Unknown"),
                            f"{scenario_prob}%"
                        )

                    with col_c:
                        st.metric(
                            "Perubahan Probabilitas",
                            f"{delta} poin",
                            delta=f"{delta} poin"
                        )

                    if delta < 0:
                        st.success(
                            f"Pada skenario ini, estimasi probabilitas risiko turun sekitar {abs(delta)} poin persentase."
                        )
                    elif delta > 0:
                        st.warning(
                            f"Pada skenario ini, estimasi probabilitas risiko naik sekitar {delta} poin persentase."
                        )
                    else:
                        st.info(
                            "Pada skenario ini, estimasi probabilitas risiko tidak berubah secara signifikan."
                        )

                    st.markdown("### 🤖 Interpretasi Agentic What-if")

                    try:
                        with st.spinner("Agentic Flow sedang membuat interpretasi simulasi what-if..."):
                            what_if_agent_answer = run_agent_what_if(
                                user_payload,
                                scenario_payload
                            )

                        with st.container(border=True):
                            st.markdown(what_if_agent_answer)

                    except Exception as e:
                        st.warning(
                            "Interpretasi agentic untuk What-if belum dapat dibuat. "
                            f"Detail teknis: {e}"
                        )

                    st.markdown("### Perbandingan Faktor Risiko")

                    def render_prediction_summary(title, prediction_data):
                        probability = probability_to_percent(
                            prediction_data.get("diabetes_probability", 0)
                        )
                        risk_level = prediction_data.get("risk_level", "Unknown")
                        contributing_factors = prediction_data.get("contributing_factors", [])

                        if risk_level == "Low":
                            badge = "🟢 Low Risk"
                        elif risk_level == "Moderate":
                            badge = "🟡 Moderate Risk"
                        elif risk_level == "High":
                            badge = "🔴 High Risk"
                        else:
                            badge = "⚪ Unknown Risk"

                        with st.container(border=True):
                            st.markdown(f"#### {title}")
                            st.markdown(f"**Risk Level:** {badge}")
                            st.markdown(f"**Diabetes Probability:** {probability}%")

                            if contributing_factors:
                                st.markdown("**Faktor yang terdeteksi:**")
                                for factor in contributing_factors:
                                    st.markdown(f"- {factor}")
                            else:
                                st.markdown(
                                    "**Faktor yang terdeteksi:** Tidak ada faktor dominan yang ditandai oleh sistem."
                                )

                            st.caption(
                                prediction_data.get(
                                    "disclaimer",
                                    "Hasil ini hanya screening awal dan bukan diagnosis medis."
                                )
                            )

                    comparison_col_1, comparison_col_2 = st.columns(2)

                    with comparison_col_1:
                        render_prediction_summary("Kondisi Saat Ini", current_prediction)

                    with comparison_col_2:
                        render_prediction_summary("Skenario What-if", scenario_prediction)

                    with st.expander("Lihat detail teknis JSON prediksi"):
                        col_json_1, col_json_2 = st.columns(2)

                        with col_json_1:
                            st.markdown("**JSON kondisi saat ini**")
                            st.json(current_prediction)

                        with col_json_2:
                            st.markdown("**JSON skenario what-if**")
                            st.json(scenario_prediction)

                except requests.exceptions.ConnectionError:
                    st.error(
                        "Tidak bisa terhubung ke FastAPI untuk simulasi. Pastikan FastAPI berjalan di http://127.0.0.1:8000."
                    )

                except requests.exceptions.HTTPError as e:
                    st.error(f"FastAPI mengembalikan HTTP error: {e}")

                    try:
                        st.code(e.response.text)
                    except Exception:
                        pass

                except Exception as e:
                    st.error(f"Terjadi error saat menjalankan What-if Simulator: {e}")

        # =====================================================
        # 7-Day Wellness Plan
        # =====================================================

        st.divider()
        st.markdown("## 🗓️ 7-Day Wellness Plan")

        st.info(
            "Rencana berikut bersifat edukatif umum berdasarkan input dan hasil model. "
            "Ini bukan instruksi medis personal."
        )

        try:
            if current_prediction_for_plan is None:
                current_prediction_for_plan = run_prediction_api(user_payload)

            wellness_plan = generate_7_day_plan(user_payload, current_prediction_for_plan)

            with st.container(border=True):
                st.markdown(wellness_plan)

        except Exception as e:
            st.error(f"Tidak dapat membuat wellness plan: {e}")


# =========================================================
# About Tab
# =========================================================

with about_tab:
    st.markdown("## ℹ️ Tentang Aplikasi")

    st.markdown(
        """
        **DiabetaCare AI** adalah aplikasi **screening awal risiko diabetes**
        berbasis AI. Aplikasi ini membantu user memahami estimasi risiko,
        faktor yang mungkin berkontribusi, serta saran gaya hidup umum.

        Aplikasi ini dibuat sebagai project portfolio/hackathon dengan menggabungkan
        machine learning, agentic workflow orchestration, tool-based reasoning, LLM explanation, dan user interface.
        """
    )

    st.warning(
        "Aplikasi ini hanya untuk edukasi dan screening awal. "
        "Hasilnya bukan diagnosis medis dan tidak menggantikan konsultasi dengan dokter atau tenaga kesehatan profesional."
    )

    st.markdown("### 🧩 Komponen Sistem")

    st.markdown(
        """
        - **Random Forest**: model machine learning untuk estimasi risiko diabetes.
        - **FastAPI**: prediction service yang menjalankan model.
        - **LangFlow Agentic Flow**: agent yang memilih tools sesuai kebutuhan user.
        - **Agent Tools**: Diabetes Prediction Tool, Form Term Explainer Tool, Red Flag Safety Tool, dan What-if Simulator Tool.
        - **Gemini**: LLM di dalam Agent untuk reasoning, tool selection, dan penjelasan hasil.
        - **Streamlit**: user interface agar user dapat mengisi form tanpa menulis JSON.
        """
    )

    st.markdown("### ⚙️ Cara Kerja Sistem")

    st.markdown(
        """
        1. User mengisi form kesehatan.
        2. Streamlit mengirim tugas ke LangFlow Agentic Flow.
        3. Agent membaca kebutuhan user dan memilih tool yang sesuai.
        4. Untuk screening, Agent memanggil Diabetes Prediction Tool.
        5. Tool tersebut memanggil FastAPI untuk menjalankan model Random Forest.
        6. Model mengembalikan risk level, probability, dan contributing factors.
        7. Agent menyusun penjelasan yang ramah user dan aman secara medis.
        8. Untuk help chat, Agent dapat memilih Form Term Explainer Tool atau Red Flag Safety Tool.
        9. Untuk simulasi, Agent dapat memilih What-if Simulator Tool.
        """
    )

    st.markdown("### 🚀 Fitur Utama")

    st.markdown(
        """
        - Form screening kesehatan yang mudah digunakan
        - BMI otomatis dari berat dan tinggi badan
        - Tanya istilah form melalui sidebar berbasis Agentic Flow
        - Prediksi risiko diabetes menggunakan Agent + Diabetes Prediction Tool
        - Penjelasan hasil dengan Gemini di dalam Agent
        - What-if Risk Simulator dengan interpretasi Agentic Flow
        - 7-Day Wellness Plan
        - Medical safety disclaimer
        """
    )

    st.markdown("### 📌 Batasan Aplikasi")

    st.markdown(
        """
        - Sistem ini tidak melakukan diagnosis medis.
        - Sistem tidak memberikan obat, dosis, atau keputusan klinis.
        - Model hanya menggunakan indikator kesehatan sederhana dari dataset.
        - Hasil perlu dikonsultasikan dengan tenaga kesehatan jika user memiliki kekhawatiran.
        """
    )


# =========================================================
# Footer
# =========================================================

st.divider()

st.caption(
    "Project portfolio: DiabetaCare AI — Agentic Diabetes Risk Screening, Education, What-if Simulator, "
    "and 7-Day Wellness Plan using Random Forest, FastAPI, LangFlow Agentic Flow, Gemini, and Streamlit. "
    "Aplikasi ini hanya untuk edukasi dan screening awal, bukan diagnosis medis."
)