import streamlit as st
import pandas as pd
import sqlite3
import io # Necesario para manejar la descarga de archivos

# --- CONFIGURACIÓN DE LA BASE DE DATOS (Mismos Helpers) ---
# (Las funciones init_db y run_query permanecen IGUALES que en el código anterior)

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    conn = sqlite3.connect('escuela.db')
    c = conn.cursor()
    
    # Tabla Alumnos
    c.execute('''
        CREATE TABLE IF NOT EXISTS alumnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            edad INTEGER,
            grado TEXT
        )
    ''')
    
    # Tabla Materias (Catálogo general)
    c.execute('''
        CREATE TABLE IF NOT EXISTS materias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT
        )
    ''')
    
    # Tabla Asignaciones (Materias Maestro - Qué materias ve cada alumno)
    c.execute('''
        CREATE TABLE IF NOT EXISTS asignaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER,
            materia_id INTEGER,
            FOREIGN KEY (alumno_id) REFERENCES alumnos (id),
            FOREIGN KEY (materia_id) REFERENCES materias (id)
        )
    ''')
    
    # Tabla Calificaciones
    c.execute('''
        CREATE TABLE IF NOT EXISTS calificaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER,
            materia_id INTEGER,
            nota REAL,
            fecha DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (alumno_id) REFERENCES alumnos (id),
            FOREIGN KEY (materia_id) REFERENCES materias (id)
        )
    ''')
    conn.commit()
    conn.close()

def run_query(query, params=(), return_data=False):
    """Función auxiliar para ejecutar consultas SQL."""
    conn = sqlite3.connect('escuela.db')
    c = conn.cursor()
    try:
        c.execute(query, params)
        if return_data:
            data = c.fetchall()
            conn.close()
            return data
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error en base de datos: {e}")
        conn.close()
        return False

# ---------------- NUEVA FUNCIÓN DE REPORTE ----------------

def generate_report_data(alumno_id):
    """Obtiene los datos del boletín de calificaciones para un alumno específico."""
    query = """
        SELECT a.nombre AS Alumno, m.nombre AS Materia, c.nota AS Calificacion, c.fecha AS Fecha
        FROM calificaciones c
        JOIN alumnos a ON c.alumno_id = a.id
        JOIN materias m ON c.materia_id = m.id
        WHERE c.alumno_id = ?
        ORDER BY m.nombre, c.fecha DESC
    """
    data = run_query(query, (alumno_id,), return_data=True)
    if data:
        df = pd.DataFrame(data, columns=['Alumno', 'Materia', 'Calificacion', 'Fecha'])
        # Calcular el promedio de las calificaciones para un resumen
        df_summary = df.groupby(['Alumno', 'Materia']).agg(
            Promedio_Materia=('Calificacion', 'mean'),
            Total_Notas=('Calificacion', 'count')
        ).reset_index()
        
        return df, df_summary
    return pd.DataFrame(), pd.DataFrame()


# --- INTERFAZ DE USUARIO ---

def main():
    st.set_page_config(page_title="Gestión Escolar", layout="wide")
    st.title("📚 Sistema de Gestión Escolar")
    
    # Inicializar DB
    init_db()

    menu = ["Alumnos", "Materias", "Asignar Materias (Maestro)", "Calificaciones"]
    choice = st.sidebar.selectbox("Navegación", menu)

    # ---------------- MÓDULO ALUMNOS (No cambia) ----------------
    if choice == "Alumnos":
        st.header("Gestión de Alumnos")
        
        tab1, tab2, tab3 = st.tabs(["➕ Nuevo Alumno", "📋 Listado", "✏️ Editar/Borrar"])
        
        with tab1:
            with st.form("add_alumno"):
                nombre = st.text_input("Nombre Completo")
                edad = st.number_input("Edad", min_value=1, max_value=100)
                grado = st.text_input("Grado/Curso")
                submitted = st.form_submit_button("Guardar Alumno")
                if submitted:
                    run_query("INSERT INTO alumnos (nombre, edad, grado) VALUES (?,?,?)", (nombre, edad, grado))
                    st.success(f"Alumno {nombre} guardado.")

        with tab2:
            data = run_query("SELECT * FROM alumnos", return_data=True)
            df = pd.DataFrame(data, columns=['ID', 'Nombre', 'Edad', 'Grado'])
            st.dataframe(df, use_container_width=True)

        with tab3:
            data = run_query("SELECT id, nombre FROM alumnos", return_data=True)
            if data:
                opciones = {f"{id} - {nombre}": id for id, nombre in data}
                seleccion = st.selectbox("Seleccionar Alumno a Editar/Borrar", list(opciones.keys()))
                id_sel = opciones.get(seleccion)
                
                # Cargar datos actuales
                datos_actuales = run_query("SELECT * FROM alumnos WHERE id=?", (id_sel,), return_data=True)[0]
                
                with st.form("edit_alumno"):
                    col1, col2 = st.columns(2)
                    new_nombre = col1.text_input("Nombre", value=datos_actuales[1])
                    new_edad = col2.number_input("Edad", value=datos_actuales[2])
                    new_grado = st.text_input("Grado", value=datos_actuales[3])
                    
                    c1, c2 = st.columns(2)
                    update = c1.form_submit_button("Actualizar")
                    delete = c2.form_submit_button("Borrar Alumno", type="primary")
                    
                    if update:
                        run_query("UPDATE alumnos SET nombre=?, edad=?, grado=? WHERE id=?", (new_nombre, new_edad, new_grado, id_sel))
                        st.success("Datos actualizados.")
                        st.rerun()
                    
                    if delete:
                        run_query("DELETE FROM alumnos WHERE id=?", (id_sel,))
                        # También borrar sus asignaciones y notas para mantener integridad
                        run_query("DELETE FROM asignaciones WHERE alumno_id=?", (id_sel,))
                        run_query("DELETE FROM calificaciones WHERE alumno_id=?", (id_sel,))
                        st.warning("Alumno eliminado.")
                        st.rerun()
            else:
                st.info("No hay alumnos registrados para editar o borrar.")


    # ---------------- MÓDULO MATERIAS (No cambia) ----------------
    elif choice == "Materias":
        st.header("Gestión de Materias")
        
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.subheader("Nueva Materia")
            with st.form("add_materia"):
                nombre_mat = st.text_input("Nombre Materia")
                desc_mat = st.text_area("Descripción")
                if st.form_submit_button("Crear Materia"):
                    run_query("INSERT INTO materias (nombre, descripcion) VALUES (?,?)", (nombre_mat, desc_mat))
                    st.success("Materia creada.")
                    st.rerun()

        with c2:
            st.subheader("Catálogo de Materias")
            data = run_query("SELECT * FROM materias", return_data=True)
            df_mat = pd.DataFrame(data, columns=['ID', 'Nombre', 'Descripción'])
            st.dataframe(df_mat, use_container_width=True)
            
            # Sección simple para borrar materias
            if not df_mat.empty:
                del_materia = st.selectbox("Borrar Materia", df_mat['Nombre'].tolist())
                if st.button("Eliminar Materia"):
                    id_mat = df_mat[df_mat['Nombre'] == del_materia]['ID'].values[0]
                    run_query("DELETE FROM materias WHERE id=?", (int(id_mat),))
                    st.rerun()

    # ---------------- MÓDULO ASIGNACIÓN (MATERIAS MAESTRO) (No cambia) ----------------
    elif choice == "Asignar Materias (Maestro)":
        st.header("Asignación de Materias por Alumno")
        st.info("Aquí defines el 'Plan de Estudios' individual de cada alumno.")

        # Obtener alumnos
        alumnos = run_query("SELECT id, nombre FROM alumnos", return_data=True)
        # Obtener materias
        materias = run_query("SELECT id, nombre FROM materias", return_data=True)

        if alumnos and materias:
            dict_alumnos = {nombre: id for id, nombre in alumnos}
            dict_materias = {nombre: id for id, nombre in materias}

            alumno_sel = st.selectbox("Selecciona un Alumno", list(dict_alumnos.keys()))
            id_alumno = dict_alumnos[alumno_sel]

            # Ver asignaciones actuales
            asignadas_raw = run_query("""
                SELECT m.nombre FROM materias m 
                JOIN asignaciones a ON m.id = a.materia_id 
                WHERE a.alumno_id = ?
            """, (id_alumno,), return_data=True)
            asignadas_actuales = [x[0] for x in asignadas_raw]

            st.write(f"Materias actualmente asignadas a **{alumno_sel}**:")
            
            # Multiselect pre-llenado con lo que ya tiene
            nuevas_asignaciones = st.multiselect(
                "Selecciona las materias para este alumno:",
                list(dict_materias.keys()),
                default=asignadas_actuales
            )

            if st.button("Guardar Asignaciones"):
                # Estrategia: Borrar todo lo anterior de este alumno y re-insertar lo seleccionado
                run_query("DELETE FROM asignaciones WHERE alumno_id=?", (id_alumno,))
                
                for materia_nombre in nuevas_asignaciones:
                    id_mat = dict_materias[materia_nombre]
                    run_query("INSERT INTO asignaciones (alumno_id, materia_id) VALUES (?,?)", (id_alumno, id_mat))
                
                st.success(f"Plan de estudios actualizado para {alumno_sel}.")
        else:
            st.warning("Necesitas registrar alumnos y materias primero.")

    # ---------------- MÓDULO CALIFICACIONES (Actualizado) ----------------
    elif choice == "Calificaciones":
        st.header("Registro y Reporte de Notas")
        
        alumnos = run_query("SELECT id, nombre FROM alumnos", return_data=True)
        
        if alumnos:
            dict_alumnos = {nombre: id for id, nombre in alumnos}
            
            # Usamos tabs para separar el ingreso del reporte
            tab_ingreso, tab_reporte = st.tabs(["📝 Ingreso de Notas", "📊 Reporte de Boletín"])

            with tab_ingreso:
                alumno_calif = st.selectbox("Calificar a:", list(dict_alumnos.keys()))
                id_alumno_calif = dict_alumnos[alumno_calif]
                
                # Solo mostrar materias asignadas a este alumno
                materias_asignadas = run_query("""
                    SELECT m.id, m.nombre FROM materias m 
                    JOIN asignaciones a ON m.id = a.materia_id 
                    WHERE a.alumno_id = ?
                """, (id_alumno_calif,), return_data=True)
                
                if materias_asignadas:
                    dict_mat_asig = {nombre: id for id, nombre in materias_asignadas}
                    
                    c1, c2, c3 = st.columns(3)
                    materia_calif = c1.selectbox("Materia", list(dict_mat_asig.keys()))
                    nota = c2.number_input("Calificación", min_value=0.0, max_value=10.0, step=0.1)
                    
                    if c3.button("Guardar Nota"):
                        id_mat_calif = dict_mat_asig[materia_calif]
                        run_query("INSERT INTO calificaciones (alumno_id, materia_id, nota) VALUES (?,?,?)", 
                                  (id_alumno_calif, id_mat_calif, nota))
                        st.success("Nota registrada.")
                        st.rerun() # Refrescar para ver la nota en la tabla
                    
                    st.divider()
                    st.subheader(f"Historial de Notas de {alumno_calif}")
                    
                    # Mostrar historial de notas
                    notas = run_query("""
                        SELECT m.nombre, c.nota, c.fecha 
                        FROM calificaciones c
                        JOIN materias m ON c.materia_id = m.id
                        WHERE c.alumno_id = ?
                        ORDER BY c.fecha DESC
                    """, (id_alumno_calif,), return_data=True)
                    
                    df_notas = pd.DataFrame(notas, columns=['Materia', 'Nota', 'Fecha'])
                    st.dataframe(df_notas, use_container_width=True)
                    
                    if not df_notas.empty:
                        promedio = df_notas['Nota'].mean()
                        st.metric("Promedio General", f"{promedio:.2f}")

                else:
                    st.warning("Este alumno no tiene materias asignadas. Ve a la sección 'Asignar Materias'.")

            with tab_reporte:
                st.subheader("Generar Reporte de Calificaciones")
                alumno_reporte = st.selectbox("Selecciona Alumno para Reporte:", list(dict_alumnos.keys()))
                id_alumno_reporte = dict_alumnos[alumno_reporte]
                
                df_all_notes, df_summary = generate_report_data(id_alumno_reporte)
                
                if not df_all_notes.empty:
                    st.markdown("#### Resumen de Promedios por Materia")
                    st.dataframe(df_summary, use_container_width=True, hide_index=True)

                    st.markdown("#### Historial Completo de Notas")
                    st.dataframe(df_all_notes, use_container_width=True, hide_index=True)
                    
                    # --- FUNCIONALIDAD DE EXPORTACIÓN ---
                    
                    # Convertir el DataFrame de Resumen a CSV
                    csv_summary = df_summary.to_csv(index=False).encode('utf-8')
                    
                    st.download_button(
                        label="Descargar Promedios (CSV)",
                        data=csv_summary,
                        file_name=f'Reporte_Promedios_{alumno_reporte.replace(" ", "_")}.csv',
                        mime='text/csv',
                    )

                    # Convertir el DataFrame Completo a Excel (mejor para reportes complejos)
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_summary.to_excel(writer, sheet_name='Resumen', index=False)
                        df_all_notes.to_excel(writer, sheet_name='Historial Completo', index=False)
                    
                    st.download_button(
                        label="Descargar Boletín Completo (Excel)",
                        data=buffer.getvalue(),
                        file_name=f'Boletin_Completo_{alumno_reporte.replace(" ", "_")}.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    )
                    st.success("Reportes listos para descargar.")
                else:
                    st.warning(f"El alumno {alumno_reporte} aún no tiene calificaciones registradas.")
        else:
            st.warning("Necesitas registrar alumnos primero.")

if __name__ == '__main__':
    main()
