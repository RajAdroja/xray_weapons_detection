// src/App.js
import React, { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

// Set default base URL for all axios requests
axios.defaults.baseURL = "http://localhost:8000";

function App() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [previewUrls, setPreviewUrls] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("results");
  const [stats, setStats] = useState({
    processed: 0,
    totalDetections: 0,
    uniqueClasses: 0,
    distribution: {},
  });
  const [modelInfo, setModelInfo] = useState({
    health: null,
    version: null,
    classes: [],
  });
  const [apiResponse, setApiResponse] = useState(null);
  const [apiLoading, setApiLoading] = useState(false);
  const [approvalStatus, setApprovalStatus] = useState({});
  const [lightbox, setLightbox] = useState({
    isOpen: false,
    imgSrc: "",
  });

  // Fetch model info once
  useEffect(() => {
    axios
      .get("/health/")
      .then((r) => setModelInfo((i) => ({ ...i, health: r.data })))
      .catch(() => {});
    axios
      .get("/version/")
      .then((r) => setModelInfo((i) => ({ ...i, version: r.data })))
      .catch(() => {});
    axios
      .get("/classes/")
      .then((r) => setModelInfo((i) => ({ ...i, classes: r.data.classes })))
      .catch(() => {});
  }, []);

  // Compute stats whenever results change
  useEffect(() => {
    if (!results.length) {
      setStats({
        processed: 0,
        totalDetections: 0,
        uniqueClasses: 0,
        distribution: {},
      });
      return;
    }
    let total = 0;
    const counts = {};
    results.forEach((r) => {
      Object.values(r.results).forEach((m) => {
        m.detections.forEach((d) => {
          total++;
          counts[d.class] = (counts[d.class] || 0) + 1;
        });
      });
    });
    setStats({
      processed: results.length,
      totalDetections: total,
      uniqueClasses: Object.keys(counts).length,
      distribution: counts,
    });
  }, [results]);

  // Escape key closes lightbox
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape" && lightbox.isOpen) closeLightbox();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [lightbox.isOpen]);

  // Handle file selection
  const handleFiles = (filesList) => {
    const files = Array.from(filesList);
    setSelectedFiles(files);

    Promise.all(
      files.map(
        (f) =>
          new Promise((res) => {
            const r = new FileReader();
            r.onload = (ev) => res(ev.target.result);
            r.readAsDataURL(f);
          })
      )
    ).then(setPreviewUrls);
  };

  // at the top of App(), after your other hooks:
  const handleApproval = async (fileIndex, modelName, approved) => {
    const block = results[fileIndex]?.results[modelName];
    if (!block) return;

    // add the approved flag here
    const approvalData = {
      filename: selectedFiles[fileIndex].name,
      model_name: modelName,
      original_base64: previewUrls[fileIndex].split(",")[1],
      detections: block.detections.map((d) => ({
        class: d.class,
        bbox: d.bbox,
        confidence: d.confidence,
      })),
      approved, // ← new
    };

    try {
      const res = await axios.post("/save-approved/", approvalData);
      console.log("Save response", res.data);
      setApprovalStatus((s) => ({
        ...s,
        [`${fileIndex}-${modelName}`]: approved,
      }));
    } catch (err) {
      console.error("Failed to save approval:", err);
    }
  };

  const handleFileChange = (e) => handleFiles(e.target.files);
  const handleDrop = (e) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };
  const handleDragOver = (e) => e.preventDefault();

  // Submit all files
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFiles.length) return;
    setLoading(true);
    setError("");
    setResults([]);
    setApprovalStatus({});

    const formData = new FormData();
    selectedFiles.forEach((f) => formData.append("files", f));

    try {
      const res = await axios.post("/predict-all/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResults(res.data);
      setActiveTab("results");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Simple API tester
  const callEndpoint = async (ep) => {
    setApiLoading(true);
    setApiResponse(null);
    try {
      const res = await axios.get(`${ep}/`);
      setApiResponse(res.data);
    } catch (err) {
      setApiResponse({ error: err.message });
    } finally {
      setApiLoading(false);
    }
  };

  const openLightbox = (src) => {
    setLightbox({ isOpen: true, imgSrc: src });
    document.body.style.overflow = "hidden";
  };
  const closeLightbox = () => {
    setLightbox({ isOpen: false, imgSrc: "" });
    document.body.style.overflow = "auto";
  };

  return (
    <div className="App">
      <header className="hero">
        <div className="hero-content">
          <h1>X-Ray Detection</h1>
          <p>
            Upload baggage scans to detect prohibited items with AI precision
          </p>
          <div className="badges">
            <span>
              <i className="fas fa-bolt" /> Fast Processing
            </span>
            <span>
              <i className="fas fa-bullseye" /> High Accuracy
            </span>
            <span>
              <i className="fas fa-search" /> Multiple Models
            </span>
            <span>
              <i className="fas fa-check-circle" /> Human Verification
            </span>
          </div>
        </div>
      </header>

      <main>
        <section className="upload-panel">
          <h2>Upload Baggage Scan Images</h2>
          <form onSubmit={handleSubmit} className="upload-form">
            <div
              className={`dropzone ${selectedFiles.length ? "has-file" : ""}`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
            >
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={handleFileChange}
              />

              {selectedFiles.length ? (
                <div className="preview-grid">
                  {selectedFiles.map((file, i) => (
                    <div key={i} className="preview-container">
                      <img
                        src={previewUrls[i]}
                        alt={file.name}
                        className="file-preview zoomable-image"
                        onClick={() => openLightbox(previewUrls[i])}
                      />
                      <div className="file-name">{file.name}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="dropzone-content">
                  <div className="upload-icon">
                    <i className="fas fa-cloud-upload-alt" />
                  </div>
                  <p>Drag & Drop your images here</p>
                  <span>or</span>
                  <label htmlFor="file-input" className="browse-button">
                    Browse Files
                  </label>
                </div>
              )}
            </div>

            <button
              type="submit"
              className={`detect-button ${loading ? "loading" : ""}`}
              disabled={loading || !selectedFiles.length}
            >
              {loading ? (
                <>
                  <div className="spinner" />
                  <span>Analyzing…</span>
                </>
              ) : (
                <>
                  <i className="fas fa-search" />
                  <span>Detect Objects</span>
                </>
              )}
            </button>
          </form>
          {error && (
            <p className="error">
              <i className="fas fa-exclamation-circle" /> {error}
            </p>
          )}
        </section>

        <nav className="tabs">
          {["results", "stats", "info", "api"].map((tab) => (
            <button
              key={tab}
              className={activeTab === tab ? "active" : ""}
              onClick={() => setActiveTab(tab)}
            >
              <i
                className={`fas fa-${
                  {
                    results: "camera",
                    stats: "chart-bar",
                    info: "info-circle",
                    api: "code",
                  }[tab]
                }`}
              />{" "}
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>

        <section className="content">
          {activeTab === "results" && (
            <div className="results">
              {results.length ? (
                results.map((res, i) => (
                  <div key={i} className="result-card">
                    <h3>Detection Result {i + 1}</h3>
                    <div className="result-images">
                      {Object.entries(res.results).map(([model, data]) => {
                        const key = `${i}-${model}`;
                        const status = approvalStatus[key];
                        return (
                          <div key={model} className="image-block">
                            <div className="model-label">{model}</div>
                            <div
                              className={`image-container ${
                                status === true
                                  ? "approved"
                                  : status === false
                                  ? "rejected"
                                  : ""
                              }`}
                            >
                              <img
                                src={`data:image/jpeg;base64,${data.image_base64}`}
                                alt={model}
                                onClick={() =>
                                  openLightbox(
                                    `data:image/jpeg;base64,${data.image_base64}`
                                  )
                                }
                                className="zoomable-image"
                              />
                              <div className="detection-count">
                                {data.detections.length}{" "}
                                {data.detections.length === 1
                                  ? "detection"
                                  : "detections"}
                              </div>
                              {status !== undefined && (
                                <div
                                  className={`verification-badge ${
                                    status ? "approved-badge" : "rejected-badge"
                                  }`}
                                >
                                  <i
                                    className={`fas ${
                                      status ? "fa-check" : "fa-times"
                                    }`}
                                  />
                                  {status ? "Approved" : "Rejected"}
                                </div>
                              )}
                            </div>
                            <div className="detections-list">
                              {data.detections.map((d, j) => (
                                <div key={j} className="detection-item">
                                  <span className="detection-class">
                                    {d.class}
                                  </span>
                                  <span className="detection-confidence">
                                    {Math.round(d.confidence * 100)}%
                                  </span>
                                </div>
                              ))}
                            </div>
                            <div className="approval-buttons">
                              <button
                                className={`approval-btn approve ${
                                  status === true ? "active" : ""
                                }`}
                                onClick={() => handleApproval(i, model, true)}
                                disabled={status !== undefined}
                              >
                                <i className="fas fa-check" /> Yes
                              </button>
                              <button
                                className={`approval-btn reject ${
                                  status === false ? "active" : ""
                                }`}
                                onClick={() => handleApproval(i, model, false)}
                                disabled={status !== undefined}
                              >
                                <i className="fas fa-times" /> No
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))
              ) : (
                <div className="placeholder">
                  <div className="placeholder-icon">
                    <i className="fas fa-camera" />
                  </div>
                  <p>No Results Yet</p>
                  <small>
                    Upload images and click “Detect Objects” to view results.
                  </small>
                </div>
              )}
            </div>
          )}

          {activeTab === "stats" && (
            <div className="stats-panel">
              <h2>Detection Statistics</h2>
              <div className="stats-overview">
                {[
                  {
                    icon: "image",
                    value: stats.processed,
                    label: "Processed Images",
                  },
                  {
                    icon: "search",
                    value: stats.totalDetections,
                    label: "Total Detections",
                  },
                  {
                    icon: "tags",
                    value: stats.uniqueClasses,
                    label: "Unique Classes",
                  },
                  {
                    icon: "check-circle",
                    value: Object.values(approvalStatus).filter((x) => x)
                      .length,
                    label: "Approved Results",
                  },
                ].map((c, i) => (
                  <div key={i} className="stat-card">
                    <div className="stat-icon">
                      <i className={`fas fa-${c.icon}`} />
                    </div>
                    <div className="stat-content">
                      <div className="stat-value">{c.value}</div>
                      <div className="stat-label">{c.label}</div>
                    </div>
                  </div>
                ))}
              </div>
              <h3>Detection Distribution</h3>
              <div className="distribution-chart">
                {stats.totalDetections ? (
                  Object.entries(stats.distribution).map(([cls, count]) => {
                    const pct = (count / stats.totalDetections) * 100;
                    return (
                      <div key={cls} className="stat-item bar">
                        <div className="bar-label">{cls}</div>
                        <div className="bar-container">
                          <div
                            className="bar-fill"
                            style={{ width: `${pct}%` }}
                            data-percentage={`${pct.toFixed(1)}%`}
                          />
                        </div>
                        <div className="bar-value">
                          {count} ({pct.toFixed(1)}%)
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="no-data">No detection data available</div>
                )}
              </div>
            </div>
          )}

          {activeTab === "info" && (
            <div className="info-panel">
              <h2>Model Information</h2>
              <div className="info-grid">
                {[
                  {
                    icon: "heartbeat",
                    label: "Health",
                    value: modelInfo.health?.status,
                  },
                  {
                    icon: "code-branch",
                    label: "API Version",
                    value: modelInfo.version?.api_version,
                  },
                  {
                    icon: "fire",
                    label: "Torch Version",
                    value: modelInfo.version?.torch_version,
                  },
                ].map((c, i) => (
                  <div key={i} className="info-item">
                    <div className="info-icon">
                      <i className={`fas fa-${c.icon}`} />
                    </div>
                    <div className="info-label">{c.label}</div>
                    <div
                      className={`info-value ${
                        c.label === "Health" && c.value === "ok"
                          ? "status-ok"
                          : ""
                      }`}
                    >
                      {c.value || "—"}
                    </div>
                  </div>
                ))}
              </div>
              <div className="info-section">
                <h3>
                  <i className="fas fa-cube" /> Available Models
                </h3>
                <div className="models-list">
                  {modelInfo.version?.models_available?.map((m) => (
                    <div key={m} className="model-badge">
                      {m}
                    </div>
                  )) || (
                    <div className="loading-placeholder">Loading models...</div>
                  )}
                </div>
              </div>
              <div className="info-section">
                <h3>
                  <i className="fas fa-tags" /> Detectable Classes
                </h3>
                <div className="class-list">
                  {modelInfo.classes.length > 0 ? (
                    modelInfo.classes.map((c) => (
                      <span key={c} className="class-tag">
                        {c}
                      </span>
                    ))
                  ) : (
                    <div className="loading-placeholder">
                      Loading classes...
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === "api" && (
            <div className="api-panel">
              <h2>Test API Endpoints</h2>
              <div className="api-buttons">
                {["health", "version", "classes", "predict-all"].map((ep) => (
                  <button
                    key={ep}
                    onClick={() => callEndpoint(`/${ep}`)}
                    disabled={apiLoading}
                    className={`api-btn ${
                      ep === "health"
                        ? "health"
                        : ep === "version"
                        ? "version"
                        : ep === "classes"
                        ? "classes"
                        : "predict"
                    }`}
                  >
                    <i
                      className={`fas fa-${
                        ep === "predict-all"
                          ? "camera"
                          : ep === "health"
                          ? "heartbeat"
                          : ep === "version"
                          ? "code-branch"
                          : "tags"
                      }`}
                    />
                    {ep
                      .replace("-", " ")
                      .replace(/\b\w/g, (l) => l.toUpperCase())}
                  </button>
                ))}
              </div>
              <div className="api-response-container">
                <div className="api-response-header">
                  <h3>Endpoint Response</h3>
                  {apiResponse && (
                    <div className="api-status">
                      Status: <span className="status-code">200 OK</span>
                    </div>
                  )}
                </div>
                <pre className="api-response">
                  {apiLoading ? (
                    <div className="api-loading">
                      <div className="spinner" />
                      <span>Fetching data...</span>
                    </div>
                  ) : (
                    JSON.stringify(apiResponse, null, 2)
                  )}
                </pre>
              </div>
            </div>
          )}
        </section>
      </main>

      {lightbox.isOpen && (
        <div className="lightbox-overlay" onClick={closeLightbox}>
          <div
            className="lightbox-container"
            onClick={(e) => e.stopPropagation()}
          >
            <button className="lightbox-close" onClick={closeLightbox}>
              <i className="fas fa-times" />
            </button>
            <img
              src={lightbox.imgSrc}
              alt="Enlarged view"
              className="lightbox-image"
            />
          </div>
        </div>
      )}

      <footer className="app-footer">
        <p>X-Ray Detection System © {new Date().getFullYear()}</p>
        <div className="footer-links">
          <a href="#about">About</a>
          <a href="#documentation">Documentation</a>
          <a href="#contact">Contact</a>
        </div>
      </footer>
    </div>
  );
}

export default App;
