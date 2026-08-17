import { ChangeEvent, DragEvent, useMemo, useState } from 'react';

type ProjectPayload = {
  project_id: string;
  manifest: {
    file_count: number;
    source_files: string[];
    docs: string[];
    logs: string[];
  };
};

type AnalysisPayload = {
  project_id: string;
  analysis: {
    language: string;
    source_files: string[];
    control_flow_signals: string[];
    business_rule_count: number;
  };
};

type BlueprintPayload = {
  project_id: string;
  blueprint: {
    rules: string[];
    edge_cases: string[];
    dependencies: string[];
  };
};

type AgentMetadata = {
  reasoning_trace?: string[];
  confidence?: number;
  needs_human_review?: boolean;
  tool_calls?: Array<{ name: string; args?: Record<string, any>; result?: any }>;
};

type GeneratePayload = {
  project_id: string;
  generated_code: string;
  generated_tests: string;
  strategy?: string;
  quality_score?: number;
  confidence?: number;
  reasoning_trace?: string[];
  tool_calls?: Array<{ name: string; args?: Record<string, any> }>;
  needs_human_review?: boolean;
};

type ExecutePayload = {
  project_id: string;
  execution?: {
    exit_code?: number;
    stdout?: string;
    stderr?: string;
    timed_out?: boolean;
  };
  status?: string;
  confidence?: number;
  reasoning_trace?: string[];
  tool_calls?: Array<{ name: string; args?: Record<string, any> }>;
  needs_human_review?: boolean;
};

type VerificationPayload = {
  project_id: string;
  match: boolean;
  legacy_outputs: string[];
  modern_outputs: string[];
  mismatches: string[];
  status?: string;
  confidence?: number;
  reasoning_trace?: string[];
  tool_calls?: Array<{ name: string; args?: Record<string, any> }>;
  needs_human_review?: boolean;
};

type ExplainPayload = {
  project_id: string;
  summary: string;
  root_cause: string;
  suggested_fix: string;
};

type StageKey = 'analyze' | 'understand' | 'generate' | 'execute' | 'verify' | 'explain';
type ViewMode = 'legacy' | 'modern';

type StageItem = {
  key: StageKey;
  label: string;
  description: string;
};

type LogEntry = {
  id: string;
  text: string;
  kind: 'info' | 'success' | 'warn' | 'error';
};

// Point to backend running via docker-compose (host port 8012 -> container 8000)
const API_BASE = 'http://localhost:8012/api';

const workflowSteps = [
  { label: 'INGEST', key: 'ingest' },
  { label: 'ANALYZE', key: 'analyze' },
  { label: 'UNDERSTAND', key: 'understand' },
  { label: 'GENERATE', key: 'generate' },
  { label: 'EXECUTE', key: 'execute' },
  { label: 'VERIFY', key: 'verify' },
  { label: 'EXPLAIN', key: 'explain' },
];

const stageList: StageItem[] = [
  { key: 'analyze', label: 'Analyze', description: 'Detect legacy rules' },
  { key: 'understand', label: 'Understand', description: 'Model behavioral graph' },
  { key: 'generate', label: 'Modernize', description: 'AI-assisted translation' },
  { key: 'verify', label: 'Verify', description: 'Deterministic comparison' },
  { key: 'explain', label: 'Explain', description: 'Root cause & fix' },
];

function App() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [project, setProject] = useState<ProjectPayload | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisPayload | null>(null);
  const [blueprint, setBlueprint] = useState<BlueprintPayload | null>(null);
  const [generation, setGeneration] = useState<GeneratePayload | null>(null);
  const [execution, setExecution] = useState<ExecutePayload | null>(null);
  const [verification, setVerification] = useState<VerificationPayload | null>(null);
  const [explain, setExplain] = useState<ExplainPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [sourcePreview, setSourcePreview] = useState('');
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('legacy');
  const [expandedStage, setExpandedStage] = useState<StageKey | null>(null);

  const stageStatus = useMemo(() => {
    const map: Record<StageKey, boolean> = {
      analyze: Boolean(analysis),
      understand: Boolean(blueprint),
      generate: Boolean(generation),
      execute: Boolean(execution),
      verify: Boolean(verification),
      explain: Boolean(explain),
    };
    return map;
  }, [analysis, blueprint, generation, execution, verification, explain]);

  const grafRules = blueprint?.blueprint.rules ?? [];
  const graphDependencies = blueprint?.blueprint.dependencies ?? [];
  const graphSignals = analysis?.analysis.control_flow_signals ?? [];

  const derivedSignalLabels = useMemo(() => {
    const matched = [...(graphSignals || [])];
    if (matched.length) {
      return [...new Set(matched.map((signal) => signal.toUpperCase()).slice(0, 3))];
    }

    const fallback = grafRules.flatMap((rule) => {
      const keywords = rule.match(/\b(IF|WHEN|MOVE|SET|CHECK|REVIEW|DISPLAY|READ|WRITE|STATUS|TOTAL)\b/gi) ?? [];
      return keywords.map((value) => value.toUpperCase());
    });
    return [...new Set(fallback)].slice(0, 3);
  }, [grafRules, graphSignals]);

  const graphNodes = graphDependencies.length
    ? graphDependencies.slice(0, 3)
    : grafRules.length
      ? grafRules.slice(0, 3).map((rule) => rule.split(/\s+/).slice(0, 2).join(' ').toUpperCase())
      : ['TOTAL', 'STATUS', 'RULE'];
  const liveGraphLabels = derivedSignalLabels.length ? derivedSignalLabels : ['IF', 'MOVE', 'CHECK'];
  const graphSummary = useMemo(() => {
    if (grafRules.length) {
      return grafRules.slice(0, 3).join(' ');
    }
    if (analysis?.analysis.business_rule_count) {
      return 'The legacy program appears to contain behavioral rules, but no explicit control-flow signals were detected in the current analysis output.';
    }
    return 'No explicit control-flow signals were detected. The system is showing the extracted understanding summary instead of a behavioral chart.';
  }, [analysis, grafRules]);
  const executeReady = Boolean(generation);

  const appendLog = (text: string, kind: LogEntry['kind'] = 'info') => {
    setLogEntries((current) => [
      ...current,
      {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        text,
        kind,
      },
    ]);
  };

  const resetSession = () => {
    setSelectedFiles([]);
    setProject(null);
    setAnalysis(null);
    setBlueprint(null);
    setGeneration(null);
    setVerification(null);
    setExplain(null);
    setError(null);
    setSourcePreview('');
    setLogEntries([]);
  };

  const buildSourcePreview = async (files: File[]) => {
    if (!files.length) {
      setSourcePreview('');
      return;
    }

    const previews: string[] = [];
    for (const file of files) {
      const text = await file.text();
      previews.push(text || `// ${file.name}\n`);
    }
    setSourcePreview(previews.join('\n\n---FILE---\n\n'));
  };

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    setSelectedFiles(files);
    await buildSourcePreview(files);
  };

  const handleDrop = async (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const files = Array.from(event.dataTransfer.files ?? []);
    setSelectedFiles(files);
    await buildSourcePreview(files);
  };

  const ingestProject = async () => {
    if (!selectedFiles.length) {
      setError('Please choose at least one legacy project file.');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const formData = new FormData();
      selectedFiles.forEach((file) => formData.append('files', file));

      const response = await fetch(`${API_BASE}/projects/ingest`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || 'Upload failed');
      }

      const payload: ProjectPayload = await response.json();
      setProject(payload);
      setAnalysis(null);
      setBlueprint(null);
      setGeneration(null);
      setVerification(null);
      setExplain(null);
      appendLog(`Project ${payload.project_id} ingested successfully.`, 'success');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      appendLog(message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const runFullPipeline = async () => {
    if (!project?.project_id) {
      setError('Upload a project first.');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const stages: Array<StageKey | 'execute'> = ['analyze', 'understand', 'generate', 'execute', 'verify', 'explain'];
      for (const stage of stages) {
        const stageUrl = `${API_BASE}/projects/${project.project_id}/${stage}`;
        const stageMethod = (stage === 'generate' || stage === 'execute') ? 'POST' : 'GET';
        const stageResponse = await fetch(stageUrl, { method: stageMethod });
        if (!stageResponse.ok) {
          const text = await stageResponse.text();
          throw new Error(`${stage} failed: ${text || 'unknown error'}`);
        }

        const stagePayload = await stageResponse.json();
        if (stage === 'analyze') {
          setAnalysis(stagePayload as AnalysisPayload);
          appendLog(`Analysis completed: ${(stagePayload as AnalysisPayload).analysis.business_rule_count ?? 0} rules detected.`, 'info');
        }
        if (stage === 'understand') {
          setBlueprint(stagePayload as BlueprintPayload);
          appendLog('Behavioral blueprint generated.', 'info');
        }
        if (stage === 'generate') {
          setGeneration(stagePayload as GeneratePayload);
          appendLog(`Generation completed: strategy=${(stagePayload as GeneratePayload).strategy}, confidence=${((stagePayload as GeneratePayload).confidence ?? 0).toFixed(2)}`, 'success');
        }
        if (stage === 'execute') {
          setExecution(stagePayload as ExecutePayload);
          appendLog(`Execution completed: exit_code=${(stagePayload as ExecutePayload).execution?.exit_code}, confidence=${((stagePayload as ExecutePayload).confidence ?? 0).toFixed(2)}`, 'info');
        }
        if (stage === 'verify') {
          setVerification(stagePayload as VerificationPayload);
          appendLog(`Verification finished: ${(stagePayload as VerificationPayload).match ? 'PASS' : 'FAIL'}, confidence=${((stagePayload as VerificationPayload).confidence ?? 0).toFixed(2)}`, (stagePayload as VerificationPayload).match ? 'success' : 'warn');
        }
        if (stage === 'explain') {
          setExplain(stagePayload as ExplainPayload);
          appendLog('Explanation created for root cause and fix.', 'success');
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      appendLog(message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const runStage = async (stage: StageKey) => {
    if (!project?.project_id) {
      setError('Upload a project first.');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      let actualStage = stage;
      if (stage === 'execute') {
        actualStage = 'execute';
      }

      const url = `${API_BASE}/projects/${project.project_id}/${actualStage}`;
      const method = (stage === 'generate' || stage === 'execute') ? 'POST' : 'GET';
      const response = await fetch(url, { method });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`${stage} failed: ${text || 'unknown error'}`);
      }

      const payload = await response.json();
      if (stage === 'analyze') {
        setAnalysis(payload as AnalysisPayload);
        appendLog(`Analysis completed: ${(payload as AnalysisPayload).analysis.business_rule_count} rules detected.`, 'info');
      }
      if (stage === 'understand') {
        setBlueprint(payload as BlueprintPayload);
        appendLog('Behavioral blueprint generated.', 'info');
      }
      if (stage === 'generate') {
        setGeneration(payload as GeneratePayload);
        appendLog(`Generation completed: strategy=${(payload as GeneratePayload).strategy}, confidence=${((payload as GeneratePayload).confidence ?? 0).toFixed(2)}`, 'success');
      }
      if (stage === 'verify') {
        setVerification(payload as VerificationPayload);
        appendLog(`Verification finished: ${(payload as VerificationPayload).match ? 'PASS' : 'FAIL'}, confidence=${((payload as VerificationPayload).confidence ?? 0).toFixed(2)}`, (payload as VerificationPayload).match ? 'success' : 'warn');
      }
      if (stage === 'explain') {
        setExplain(payload as ExplainPayload);
        appendLog('Explanation created for root cause and fix.', 'success');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      appendLog(message, 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`app view-${viewMode}`}>
      <header className="top">
        <div className="brand">
          <svg className="mark" viewBox="0 0 64 64" aria-hidden="true">
            <rect x="8" y="8" width="48" height="48" rx="12" fill="rgba(63,198,240,0.18)" stroke="rgba(63,198,240,0.6)" />
            <path d="M20 39L28 25L36 39M23 33H35" stroke="#7dd3fc" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M38 20H46V48H38" stroke="#8b7cff" strokeWidth="3" fill="none" strokeLinecap="round" />
          </svg>
          <div>
            <h1>LEGACY-X</h1>
            <div className="sub">Behavioral verification platform</div>
          </div>
        </div>

        <div className="headctl">
          <div className="segmented" aria-label="Mode selector">
            <button type="button" className={viewMode === 'legacy' ? 'active' : ''} onClick={() => setViewMode('legacy')}>
              Legacy
            </button>
            <button type="button" className={viewMode === 'modern' ? 'active' : ''} onClick={() => setViewMode('modern')}>
              Modern
            </button>
          </div>
          <button type="button" className="btn ghost small" onClick={resetSession}>Reset</button>
          <button type="button" className="btn primary small" onClick={() => ingestProject()} disabled={!selectedFiles.length || loading}>
            Analyze legacy code
          </button>
          <button type="button" className="btn small" onClick={runFullPipeline} disabled={!project || loading}>
            Run full pipeline
          </button>
        </div>
      </header>

      <div className="stepper-wrap">
        <div className="stepper">
          {workflowSteps.map((step, index) => {
            const active = step.key === 'ingest' ? Boolean(project)
              : step.key === 'analyze' ? Boolean(analysis)
              : step.key === 'understand' ? Boolean(blueprint)
              : step.key === 'generate' ? Boolean(generation)
              : step.key === 'execute' ? executeReady
              : step.key === 'verify' ? Boolean(verification)
              : Boolean(explain);
            const done = step.key === 'analyze' && Boolean(analysis)
              || step.key === 'understand' && Boolean(blueprint)
              || step.key === 'generate' && Boolean(generation)
              || step.key === 'execute' && executeReady
              || step.key === 'verify' && Boolean(verification)
              || step.key === 'explain' && Boolean(explain)
              || step.key === 'ingest' && Boolean(project);
            return (
              <div key={step.key} className={`step ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
                {index > 0 && <div className={`connector ${done ? 'done' : ''}`} />}
                <div className="dot">{index + 1}</div>
                <div className="label">{step.label}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="stage-tabs">
        {stageList.map((stage, index) => {
          const done = stage.key === 'analyze' ? Boolean(analysis) : stage.key === 'understand' ? Boolean(blueprint) : stage.key === 'generate' ? Boolean(generation) : stage.key === 'verify' ? Boolean(verification) : Boolean(explain);
          const active = stage.key === 'analyze' ? Boolean(analysis) : stage.key === 'understand' ? Boolean(blueprint) : stage.key === 'generate' ? Boolean(generation) : stage.key === 'verify' ? Boolean(verification) : Boolean(explain);
          return (
            <button type="button" key={stage.key} className={`stage-tab ${done ? 'complete' : ''} ${active ? 'active' : ''}`} onClick={() => runStage(stage.key)} disabled={loading || !project}>
              <span className="num">{index + 1}</span>
              <span>
                <div className="tt">{stage.label}</div>
                <div className="ts">{stage.description}</div>
              </span>
              {done && <span className="check">✓</span>}
            </button>
          );
        })}
      </div>

      {viewMode === 'legacy' ? (
        <section className="panel">
          <div className="ph">
            <div className="t"><span className="dot-mini" /> Legacy analyzer</div>
            <span className="badge blue">act</span>
          </div>

          <div className="pb grid2">
            <div>
              <div className="editor-shell">
                <div className="gutter">
                  {Array.from({ length: 15 }, (_, i) => (
                    <div key={i}>{i + 1}</div>
                  ))}
                </div>
                <pre className="codeview">{sourcePreview || 'Upload a project to inspect legacy source files here.'}</pre>
              </div>

              <div className="stat-row">
                <div className="stat">
                  <div className="n">{analysis?.analysis.business_rule_count ?? 0}</div>
                  <div className="l">Rules</div>
                </div>
                <div className="stat">
                  <div className="n">{analysis?.analysis.control_flow_signals.length ?? 0}</div>
                  <div className="l">Signals</div>
                </div>
                <div className="stat">
                  <div className="n">{project?.manifest.file_count ?? 0}</div>
                  <div className="l">Files</div>
                </div>
              </div>

              <div className="action-row">
                <label className={`file-chip ${isDragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop}>
                  <input type="file" multiple onChange={handleFileChange} />
                  <span>Upload</span>
                </label>
                <button type="button" className="btn primary small" onClick={() => ingestProject()} disabled={loading || !selectedFiles.length}>Upload project</button>
                <button type="button" className="btn small" onClick={() => runStage('analyze')} disabled={loading || !project}>Analyze</button>
                <button type="button" className="btn small" onClick={runFullPipeline} disabled={loading || !project}>Run full pipeline</button>
              </div>

              {error && <div className="error-box">{error}</div>}
            </div>

            <div>
              <div className="graph-card">
                <div className="graph-head">
                  <span className="badge violet">Rule graph</span>
                  <span className="badge good">Behavioral</span>
                </div>

                {graphSignals.length ? (
                  <div className="graph-scroll">
                    <svg viewBox="0 0 500 260" className="graph-svg" role="img" aria-label="Behavioral graph">
                      <line x1="70" y1="90" x2="220" y2="90" stroke="#283a57" strokeWidth="2" />
                      <line x1="220" y1="90" x2="370" y2="60" stroke="#283a57" strokeWidth="2" />
                      <line x1="220" y1="90" x2="370" y2="160" stroke="#283a57" strokeWidth="2" />
                      <line x1="370" y1="60" x2="460" y2="60" stroke="#283a57" strokeWidth="2" />
                      <line x1="370" y1="160" x2="460" y2="160" stroke="#283a57" strokeWidth="2" />
                      <circle cx="70" cy="90" r="26" fill="rgba(63,198,240,0.12)" stroke="#3fc6f0" />
                      <circle cx="220" cy="90" r="26" fill="rgba(139,124,255,0.12)" stroke="#8b7cff" />
                      <circle cx="370" cy="60" r="24" fill="rgba(52,211,153,0.12)" stroke="#34d399" />
                      <circle cx="370" cy="160" r="24" fill="rgba(251,191,36,0.12)" stroke="#fbbf24" />
                      <circle cx="460" cy="60" r="18" fill="rgba(52,211,153,0.12)" stroke="#34d399" />
                      <circle cx="460" cy="160" r="18" fill="rgba(251,191,36,0.12)" stroke="#fbbf24" />
                      <text x="70" y="96" textAnchor="middle" fill="#e7edf8" fontSize="10">{liveGraphLabels[0] || 'INPUT'}</text>
                      <text x="220" y="96" textAnchor="middle" fill="#e7edf8" fontSize="10">{liveGraphLabels[1] || 'CHECK'}</text>
                      <text x="370" y="66" textAnchor="middle" fill="#e7edf8" fontSize="10">{graphNodes[0] || 'RULE'}</text>
                      <text x="370" y="166" textAnchor="middle" fill="#e7edf8" fontSize="10">{graphNodes[1] || 'RESULT'}</text>
                      <text x="460" y="64" textAnchor="middle" fill="#e7edf8" fontSize="9">{graphNodes[2]?.slice(0, 4).toUpperCase() || 'OK'}</text>
                      <text x="460" y="164" textAnchor="middle" fill="#e7edf8" fontSize="9">WARN</text>
                    </svg>
                  </div>
                ) : (
                  <div className="graph-summary-box">
                    <div className="graph-summary-title">Understanding summary</div>
                    <p>{graphSummary}</p>
                  </div>
                )}

                <div className="graph-legend">
                  <span><b>Rules</b> {grafRules.length}</span>
                  <span><b>Dependencies</b> {graphDependencies.length}</span>
                  <span><b>Control flow</b> {graphSignals.length} signals</span>
                </div>

                <div className="rule-stack">
                  {grafRules.length ? (
                    grafRules.map((rule, index) => (
                      <div key={`${rule}-${index}`} className="rule-card"><span className="rid">R{index + 1}</span>{rule}</div>
                    ))
                  ) : (
                    <div className="rule-card muted">No behavioral rules yet. Run the analysis pipeline to populate the dependency graph.</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <section className="panel">
          <div className="ph">
            <div className="t"><span className="dot-mini" /> Modern pipeline</div>
            <span className="badge violet">live</span>
          </div>

          <div className="pb modern-grid">
            <div className="modern-card">
              <div className="modern-card-header">
                <span className="modern-badge">1</span>
                <h3>AI-assisted translation</h3>
                {generation && (
                  <div className="card-meta">
                    <span className={`conf-badge ${(generation.confidence ?? 0) > 0.8 ? 'high' : (generation.confidence ?? 0) > 0.5 ? 'med' : 'low'}`}>
                      {((generation.confidence ?? 0) * 100).toFixed(0)}% confidence
                    </span>
                    {generation.needs_human_review && <span className="review-badge">Review needed</span>}
                  </div>
                )}
              </div>
              <pre className="modern-code">{generation?.generated_code || 'Run the generation stage to produce the modernized translation.'}</pre>
              {generation && generation.reasoning_trace && (
                <details className="metadata-section">
                  <summary>Generation reasoning ({generation.reasoning_trace.length} steps)</summary>
                  <ul className="trace-list">
                    {generation.reasoning_trace.slice(0, 5).map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>

            <div className="modern-card">
              <div className="modern-card-header">
                <span className="modern-badge alt">2</span>
                <h3>Execute & Verify</h3>
              </div>
              <div className="modern-status">
                {execution && (
                  <div className="execution-summary">
                    {execution.status && (
                      <div className={`status-banner ${execution.status.includes('SUCCESS') ? 'success' : execution.status.includes('FAILED') ? 'error' : execution.status.includes('TIMEOUT') ? 'warn' : 'neutral'}`}>
                        <strong>{execution.status}</strong>
                      </div>
                    )}
                    <div className="stat-pair">
                      <span>Exit code:</span>
                      <strong>{execution.execution?.exit_code ?? (execution.execution?.timed_out ? 'TIMEOUT' : 'N/A')}</strong>
                    </div>
                    <div className="stat-pair">
                      <span>Timed out:</span>
                      <strong>{execution.execution?.timed_out ? '⚠️ Yes' : '✓ No'}</strong>
                    </div>
                    <div className="stat-pair">
                      <span>Confidence:</span>
                      <strong className={`conf-badge ${(execution.confidence ?? 0) > 0.8 ? 'high' : (execution.confidence ?? 0) > 0.5 ? 'med' : 'low'}`}>
                        {((execution.confidence ?? 0) * 100).toFixed(0)}%
                      </strong>
                    </div>
                  </div>
                )}
                <div className={`status-pill ${verification?.match ? 'success' : verification?.status === 'FAIL' ? 'error' : 'warn'}`}>
                  {verification?.status ? verification.status : (verification ? (verification.match ? '✓ Match' : '✗ Mismatch') : 'Awaiting verification')}
                </div>
                {verification && (
                  <div className="verify-confidence">
                    Verification confidence: {((verification.confidence ?? 0) * 100).toFixed(0)}% {verification.needs_human_review && '⚠️ Requires review'}
                  </div>
                )}
                <ul>
                  {verification?.mismatches?.length ? (
                    <>
                      <li><strong>{verification.mismatches.length} mismatch(es) found:</strong></li>
                      {verification.mismatches.slice(0, 3).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
                      {verification.mismatches.length > 3 && <li>...and {verification.mismatches.length - 3} more</li>}
                    </>
                  ) : (
                    <li>✓ No mismatches detected.</li>
                  )}
                </ul>
              </div>
            </div>

            <div className="modern-card">
              <div className="modern-card-header">
                <span className="modern-badge alt2">3</span>
                <h3>Explain</h3>
              </div>
              <div className="modern-status">
                <p>{explain?.summary || 'Run the explain stage to review the root cause and remediation plan.'}</p>
                <div className="mini-block">
                  <strong>Root cause</strong>
                  <span>{explain?.root_cause || 'Not available yet.'}</span>
                </div>
                <div className="mini-block">
                  <strong>Suggested fix</strong>
                  <span>{explain?.suggested_fix || 'Not available yet.'}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="panel">
        <div className="ph">
          <div className="t"><span className="dot-mini" /> Activity log</div>
          <button type="button" className="btn ghost small" onClick={() => setLogEntries([])}>Clear</button>
        </div>

        <div className="pb">
          {logEntries.length ? (
            logEntries.map((entry) => (
              <div key={entry.id} className={`log-line ${entry.kind === 'success' ? 'success' : entry.kind === 'error' ? 'error' : entry.kind === 'warn' ? 'warn' : ''}`}>
                {entry.text}
              </div>
            ))
          ) : (
            <div className="log-line">No project activity yet. Upload a legacy codebase to begin.</div>
          )}
        </div>
      </section>
    </div>
  );
}

export default App;
