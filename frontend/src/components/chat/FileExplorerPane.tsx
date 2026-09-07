"use client";

import * as React from "react";
import { Folder, File, ChevronRight, ChevronDown, FileText, X } from "lucide-react";
import { ApiClient } from "@/lib/api";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { materialLight } from "react-syntax-highlighter/dist/cjs/styles/prism";

interface FileExplorerPaneProps {
  projectId: string;
  onClose?: () => void;
}

interface FileNode {
  name: string;
  path: string;
  is_dir: boolean;
  size: number | null;
}

export function FileExplorerPane({ projectId, onClose }: FileExplorerPaneProps) {
  const [files, setFiles] = React.useState<FileNode[]>([]);
  const [currentPath, setCurrentPath] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [selectedFile, setSelectedFile] = React.useState<string | null>(null);
  const [fileContent, setFileContent] = React.useState<string | null>(null);
  const [loadingFile, setLoadingFile] = React.useState(false);

  React.useEffect(() => {
    loadFiles("");
  }, [projectId]);

  async function loadFiles(path: string) {
    setLoading(true);
    try {
      const data = await ApiClient.listProjectFiles(projectId, path);
      setFiles(data.files || []);
      setCurrentPath(path);
    } catch (err) {
      console.error("Failed to load files", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleFileClick(file: FileNode) {
    if (file.is_dir) {
      loadFiles(file.path);
      setSelectedFile(null);
      setFileContent(null);
    } else {
      setSelectedFile(file.path);
      setLoadingFile(true);
      try {
        const data = await ApiClient.getFileContent(projectId, file.path);
        setFileContent(data.content);
      } catch (err) {
        setFileContent("Error loading file content");
      } finally {
        setLoadingFile(false);
      }
    }
  }

  function handleBack() {
    if (!currentPath) return;
    const parts = currentPath.split("/");
    parts.pop();
    loadFiles(parts.join("/"));
    setSelectedFile(null);
    setFileContent(null);
  }

  return (
    <div className="flex flex-col h-full bg-[#fcfcfc] border-l border-gray-200 w-80 flex-shrink-0 shadow-[-4px_0_15px_-3px_rgba(0,0,0,0.05)]">
      <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-white">
        <h3 className="text-sm font-semibold text-gray-800 flex items-center">
          <Folder size={16} className="text-indigo-500 mr-2" />
          Project Files
        </h3>
        {onClose && (
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={16} />
          </button>
        )}
      </div>

      {selectedFile ? (
        <div className="flex flex-col h-full overflow-hidden">
          <div className="flex items-center p-2 border-b border-gray-100 bg-gray-50">
            <button 
              onClick={() => { setSelectedFile(null); setFileContent(null); }}
              className="text-[11px] text-indigo-600 hover:text-indigo-800 font-medium mr-2"
            >
              ← Back
            </button>
            <span className="text-xs font-mono text-gray-600 truncate">{selectedFile.split("/").pop()}</span>
          </div>
          <div className="flex-1 overflow-auto bg-white p-2">
            {loadingFile ? (
              <div className="text-xs text-gray-400 text-center mt-10">Loading...</div>
            ) : (
              <SyntaxHighlighter
                style={materialLight as any}
                language={selectedFile.split(".").pop() || "text"}
                className="text-[11px] !m-0 !bg-transparent"
                PreTag="div"
              >
                {fileContent || ""}
              </SyntaxHighlighter>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          {currentPath && (
            <button 
              onClick={handleBack}
              className="flex items-center w-full p-2 hover:bg-gray-100 text-left transition-colors border-b border-gray-100"
            >
              <span className="text-[12px] font-medium text-gray-600">.. (Up a dir)</span>
            </button>
          )}
          
          {loading ? (
            <div className="p-4 text-xs text-gray-400 text-center">Loading...</div>
          ) : files.length === 0 ? (
            <div className="p-4 text-xs text-gray-400 text-center italic">Empty directory</div>
          ) : (
            <div className="py-1">
              {files.map((file) => (
                <button
                  key={file.path}
                  onClick={() => handleFileClick(file)}
                  className="flex items-center w-full px-3 py-1.5 hover:bg-indigo-50 text-left transition-colors group"
                >
                  {file.is_dir ? (
                    <Folder size={14} className="text-indigo-400 mr-2 flex-shrink-0 group-hover:text-indigo-600" />
                  ) : (
                    <FileText size={14} className="text-gray-400 mr-2 flex-shrink-0 group-hover:text-gray-600" />
                  )}
                  <span className="text-[13px] text-gray-700 truncate">{file.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
