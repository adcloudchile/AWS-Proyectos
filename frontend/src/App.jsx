import React, { useState, useCallback } from 'react';
import axios from 'axios';
import ReactFlow, { Background, Controls } from 'reactflow';
import 'reactflow/dist/style.css';
import { Upload, FileJson, CheckCircle, AlertCircle, Play, Download, Code } from 'lucide-react';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';
import 'prismjs/components/prism-python';

// --- CONFIGURACIÓN ---
// Tu URL real de AWS API Gateway
const API_ENDPOINT = "https://kjgsdv2xja.execute-api.us-east-1.amazonaws.com/firmar-url";

// Nodos del diagrama de flujo visual
const initialNodes = [
  { id: '1', position: { x: 250, y: 0 }, data: { label: 'Inicio (S3)' }, style: { background: '#334155', color: '#fff' } },
  { id: '2', position: { x: 250, y: 100 }, data: { label: '🤖 Agente Analista' } },
  { id: '3', position: { x: 250, y: 200 }, data: { label: '🧠 Agente Estratega' } },
  { id: '4', position: { x: 250, y: 300 }, data: { label: '👷 Agente Generador' } },
  { id: '5', position: { x: 250, y: 400 }, data: { label: 'Fin (Script.py)' }, type: 'output' },
];
const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e2-3', source: '2', target: '3', animated: true },
  { id: 'e3-4', source: '3', target: '4', animated: true },
  { id: 'e4-5', source: '4', target: '5', animated: true },
];

export default function App() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, uploading, processing, done, error
  const [scriptContent, setScriptContent] = useState('');
  const [nodes, setNodes] = useState(initialNodes);

  // Función para actualizar colores del diagrama según progreso
  const updateFlowStep = (stepIndex) => {
    setNodes((nds) =>
      nds.map((node, index) => {
        if (index <= stepIndex) {
          return { ...node, style: { ...node.style, background: '#10b981', color: '#fff', border: '2px solid #fff' } };
        }
        return node;
      })
    );
  };

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setStatus('idle');
    setScriptContent('');
    setNodes(initialNodes);
  };

  const processFile = async () => {
    if (!file) return;
    setStatus('uploading');
    updateFlowStep(0);

    try {
      // 1. Obtener URL firmada para SUBIR (PUT)
      console.log("Pidiendo permiso para subir...");
      const firmarSubida = await axios.post(API_ENDPOINT, {
        accion: 'subir',
        archivo: file.name
      });
      const { url: uploadUrl } = firmarSubida.data;

      // 2. Subir archivo a S3 directamente
      console.log("Subiendo a S3...");
      await axios.put(uploadUrl, file, {
        headers: { 'Content-Type': file.type }
      });

      setStatus('processing');
      simulateProcessing(); // Simulación visual mientras AWS trabaja
      pollForResult(file.name); // Comenzar a preguntar si ya está listo

    } catch (err) {
      console.error(err);
      setStatus('error');
      alert("Error al subir archivo. Revisa la consola (F12) para más detalles.");
    }
  };

  // Simulación visual para entretener al usuario
  const simulateProcessing = () => {
    setTimeout(() => updateFlowStep(1), 2000); // Analista
    setTimeout(() => updateFlowStep(2), 5000); // Estratega
    setTimeout(() => updateFlowStep(3), 8000); // Generador
  };

  // Polling: Preguntar cada 3 segundos si el resultado existe
  const pollForResult = async (filename) => {
    const cleanName = filename.replace('.json', '') + '.py';
    let intentos = 0;
    const maxIntentos = 30; // 1.5 minutos aprox

    const interval = setInterval(async () => {
      intentos++;
      try {
        console.log(`Intento ${intentos}: Buscando resultado...`);

        // Pedir URL firmada para DESCARGAR (GET)
        const firmarBajada = await axios.post(API_ENDPOINT, {
          accion: 'bajar',
          archivo: cleanName
        });

        const { url: downloadUrl } = firmarBajada.data;

        // Intentar descargar el script
        const response = await axios.get(downloadUrl);

        if (response.status === 200) {
          clearInterval(interval);
          setScriptContent(response.data);
          setStatus('done');
          updateFlowStep(4);
          // Colorear código
          setTimeout(() => Prism.highlightAll(), 100);
        }
      } catch (err) {
        // Si da 404 es que aun no está listo, seguimos intentando
        if (intentos >= maxIntentos) {
          clearInterval(interval);
          setStatus('error');
          alert("Tiempo de espera agotado. Revisa AWS Step Functions.");
        }
      }
    }, 3000);
  };

  return (
    <div className="min-h-screen p-8 flex flex-col items-center max-w-6xl mx-auto font-sans">
      <header className="mb-10 text-center">
        <h1 className="text-5xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400 pb-2">
          Agente Forense AWS AI
        </h1>
        <p className="text-slate-400 mt-2 text-lg">Sube tu reporte de incidentes y deja que la IA lo repare</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 w-full h-[600px]">

        {/* PANEL IZQUIERDO: Carga y Flujo */}
        <div className="flex flex-col gap-4 h-full">
          <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-xl">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-white">
              <Upload size={20} className="text-blue-400" /> Cargar Reporte JSON
            </h2>
            <div className="flex gap-4">
              <input
                type="file"
                accept=".json"
                onChange={handleFileChange}
                className="block w-full text-sm text-slate-300
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-full file:border-0
                  file:text-sm file:font-semibold
                  file:bg-blue-600 file:text-white
                  file:cursor-pointer hover:file:bg-blue-700
                  cursor-pointer
                "
              />
              <button
                onClick={processFile}
                disabled={!file || status === 'processing'}
                className={`px-6 py-2 rounded-lg font-bold transition-all flex items-center gap-2 shadow-lg
                  ${status === 'processing' ? 'bg-slate-600 cursor-not-allowed opacity-50' : 'bg-emerald-500 hover:bg-emerald-600 text-white transform hover:scale-105'}
                `}
              >
                {status === 'processing' ? 'Procesando...' : <><Play size={18} /> Iniciar</>}
              </button>
            </div>
          </div>

          {/* Diagrama de Flujo (React Flow) */}
          <div className="flex-1 bg-slate-900 rounded-xl border border-slate-700 overflow-hidden relative shadow-inner">
            <ReactFlow
              nodes={nodes}
              edges={initialEdges}
              fitView
              proOptions={{ hideAttribution: true }}
            >
              <Background color="#475569" gap={20} />
              <Controls className="bg-slate-800 border-slate-600 fill-white" />
            </ReactFlow>
            {status === 'processing' && (
              <div className="absolute top-4 right-4 bg-blue-600/90 backdrop-blur text-xs px-3 py-1 rounded-full animate-pulse text-white font-bold shadow-lg">
                IA TRABAJANDO...
              </div>
            )}
          </div>
        </div>

        {/* PANEL DERECHO: Resultado */}
        <div className="bg-[#1e1e1e] rounded-xl border border-slate-700 flex flex-col overflow-hidden shadow-2xl h-full">
          <div className="bg-slate-800 p-4 border-b border-slate-700 flex justify-between items-center">
            <h2 className="font-mono text-sm flex items-center gap-2 text-emerald-400 font-bold">
              <Code size={16} />
              Resultado: script_remediacion.py
            </h2>
            {status === 'done' && (
              <span className="text-xs bg-emerald-500/20 text-emerald-300 px-3 py-1 rounded-full flex items-center gap-1 border border-emerald-500/30">
                <CheckCircle size={12} /> Generado con Gemini 2.0
              </span>
            )}
          </div>

          <div className="flex-1 overflow-auto p-0 relative">
            {status === 'idle' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-600">
                <FileJson size={64} className="mb-4 opacity-50" />
                <p className="font-medium">Esperando archivo...</p>
              </div>
            )}
            {status === 'processing' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-blue-400">
                <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-6"></div>
                <p className="text-lg font-semibold animate-pulse">Analizando Logs y Generando Código...</p>
                <p className="text-sm text-slate-500 mt-2">Esto toma unos 20-30 segundos</p>
              </div>
            )}
            {status === 'error' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-red-400">
                <AlertCircle size={64} className="mb-4" />
                <p className="font-bold text-lg">Ocurrió un error</p>
                <p className="text-sm text-slate-500">Revisa la consola para más detalles.</p>
              </div>
            )}

            {/* Área de código */}
            <pre className={`language-python m-0 p-4 min-h-full ${status === 'done' ? 'block' : 'hidden'}`}>
              <code className="text-sm font-mono">{scriptContent}</code>
            </pre>
          </div>
        </div>

      </div>
    </div>
  );
}