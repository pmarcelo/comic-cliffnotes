import streamlit as st
import pandas as pd
from sqlalchemy import text, delete
from database.models import ProcessingQueue, QueueStatus
from datetime import datetime

def fetch_queue_data(engine):
    """
    Fetches raw UTC data from the database and converts to local PST/PDT in Python.
    """
    query = text("""
        SELECT 
            q.id, s.title, q.action, 
            LOWER(q.status::TEXT) as status, 
            q.priority, 
            q.created_at, 
            q.updated_at, 
            q.error_log
        FROM processing_queue q
        JOIN series s ON q.series_id = s.id
        ORDER BY 
            CASE WHEN LOWER(q.status::TEXT) = 'running' THEN 1 
                 WHEN LOWER(q.status::TEXT) = 'pending' THEN 2 
                 ELSE 3 END,
            q.priority ASC, q.created_at DESC
    """)
    df = pd.read_sql(query, engine)
    
    # PST/PDT Conversion
    for col in ['created_at', 'updated_at']:
        if not df[col].empty:
            df[col] = pd.to_datetime(df[col], utc=True).dt.tz_convert('America/Los_Angeles').dt.tz_localize(None)
            
    return df

@st.fragment
def render_queue_tab(engine):
    """
    The Mission Control fragment. 
    """
    col_header, col_refresh = st.columns([5, 1])
    with col_header:
        st.subheader("PIPELINE MISSION CONTROL")
    with col_refresh:
        if st.button("REFRESH DATA", use_container_width=True):
            st.rerun(scope="fragment")
    
    df = fetch_queue_data(engine)

    # Health Check Status
    pending_count = len(df[df['status'] == 'pending'])
    running_count = len(df[df['status'] == 'running'])

    if pending_count > 0 and running_count == 0:
        st.warning(f"WORKER OFFLINE: {pending_count} tasks waiting, but no local workers detected.")
    elif running_count > 0:
        st.success(f"WORKER ACTIVE: Processing {running_count} task(s) on local host.")
    else:
        st.info("WORKER STATUS: Idle.")

    st.divider()

    st.write("### WORKER COMMANDS")
    st.caption("Run these locally to start processing.")
    c_gen, c_ocr, c_sum = st.columns(3)
    with c_gen:
        st.code("python core/pipeline/queue_worker.py", language="bash")
    with c_ocr:
        st.code("python core/pipeline/queue_worker.py --lane ocr", language="bash")
    with c_sum:
        st.code("python core/pipeline/queue_worker.py --lane summary", language="bash")
    st.divider()

    col_ref_text, col_clear = st.columns([5, 1])
    with col_ref_text:
        st.caption("Monitoring background worker activity and task priority.")

    with col_clear:
        if st.button("CLEAR COMPLETED", use_container_width=True):
            with engine.begin() as conn:
                conn.execute(delete(ProcessingQueue).where(ProcessingQueue.status == QueueStatus.COMPLETED))
            st.rerun(scope="fragment")

    if df.empty:
        st.info("The queue is currently empty.")
        return

    df['id'] = df['id'].astype(str)

    # 1. Active / Running Tasks
    running = df[df['status'] == 'running']
    if not running.empty:
        st.write("### CURRENTLY RUNNING")
        for _, row in running.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                updated_at = row['updated_at']
                run_time = datetime.now() - updated_at
                minutes = int(run_time.total_seconds() // 60)
                
                c1.markdown(f"**{row['title']}** - {row['action'].upper()}")
                c1.caption(f"Started {minutes}m ago")

                if c2.button("STOP TASK", key=f"stop_{row['id']}", type="primary", use_container_width=True):
                    with engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE processing_queue
                            SET status = 'FAILED'::queuestatus,
                                error_log = 'Task stopped manually by user.'
                            WHERE id = :id
                        """), {"id": row['id']})
                    st.rerun(scope="fragment")

    # 2. The Full Queue Table
    st.write("### TASK HISTORY")
    
    def color_status(val):
        color = 'gray'
        if val == 'completed': color = '#2ecc71'
        if val == 'failed': color = '#e74c3c'
        if val == 'running': color = '#3498db'
        if val == 'pending': color = '#f1c40f'
        return f'color: {color}; font-weight: bold;'

    st.dataframe(
        df.style.map(color_status, subset=['status']),
        column_config={
            "id": None,
            "title": "Series",
            "action": "Task",
            "status": "Status",
            "priority": st.column_config.NumberColumn("Priority", format="%d"),
            "created_at": st.column_config.DatetimeColumn("Queued", format="h:mm a"),
            "updated_at": None,
            "error_log": "Last Error"
        },
        hide_index=True,
        use_container_width=True
    )

    # 3. Task Management
    st.divider()
    manage_col1, manage_col2 = st.columns(2)

    with manage_col1:
        pending_tasks = df[df['status'] == 'pending']
        if not pending_tasks.empty:
            st.write("### PENDING TASKS")
            for _, row in pending_tasks.iterrows():
                with st.expander(f"Cancel: {row['title']}"):
                    if st.button(f"REMOVE", key=f"del_pending_{row['id']}", use_container_width=True):
                        with engine.begin() as conn:
                            conn.execute(delete(ProcessingQueue).where(ProcessingQueue.id == row['id']))
                        st.rerun(scope="fragment")

    with manage_col2:
        failed_tasks = df[df['status'] == 'failed']
        if not failed_tasks.empty:
            st.write("### RECOVERY ACTIONS")
            for _, row in failed_tasks.iterrows():
                with st.expander(f"Fix: {row['title']}"):
                    st.error(f"Error: {row['error_log']}")
                    r1, r2 = st.columns(2)
                    if r1.button(f"RETRY", key=f"retry_{row['id']}", use_container_width=True):
                        with engine.begin() as conn:
                            conn.execute(text("UPDATE processing_queue SET status = 'PENDING'::queuestatus, error_log = NULL WHERE id = :id"), {"id": row['id']})
                        st.rerun(scope="fragment")
                    if r2.button(f"DEL", key=f"del_failed_{row['id']}", use_container_width=True):
                        with engine.begin() as conn:
                            conn.execute(delete(ProcessingQueue).where(ProcessingQueue.id == row['id']))
                        st.rerun(scope="fragment")