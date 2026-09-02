"use client";

import * as React from "react";
import { Database, UploadCloud, Search, FileText, Tag, Loader2, BookOpen, CheckCircle, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";

export default function KnowledgePage() {
  const [documents, setDocuments] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [searchResults, setSearchResults] = React.useState<any>(null);
  const [searching, setSearching] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    loadDocs();
  }, []);

  async function loadDocs() {
    try {
      setLoading(true);
      const data = await ApiClient.listFiles();
      setDocuments(data);
    } catch (err) {
      console.error("Failed to load documents", err);
    } finally {
      setLoading(false);
    }
  }

  const handleSearch = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && searchQuery.trim()) {
      try {
        setSearching(true);
        setSearchResults(null);
        const results = await ApiClient.searchKB(searchQuery);
        setSearchResults(results);
      } catch (err) {
        console.error(err);
      } finally {
        setSearching(false);
      }
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      try {
        setUploading(true);
        const formData = new FormData();
        formData.append("file", file);
        await ApiClient.uploadFile(formData);
        await loadDocs(); // Refresh document list
      } catch (err: any) {
        alert(`Upload failed: ${err.message}`);
      } finally {
        setUploading(false);
        // Reset file input
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    }
  };

  return (
    <div className="flex-1 overflow-auto p-4 md:p-6 lg:p-8 flex flex-col relative">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-xl font-bold tracking-tight">Knowledge Base</h1>
              <p className="text-sm text-gray-500 mt-0.5">Permission-aware RAG documents and vector search (FR5).</p>
            </div>
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              onChange={handleFileUpload} 
            />
            <Button 
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs shadow-sm" 
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? (
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : (
                <UploadCloud className="w-3.5 h-3.5 mr-1.5" />
              )}
              {uploading ? "Uploading..." : "Upload Document"}
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 flex-1">
            {/* Search Panel */}
            <div className="lg:col-span-1 rounded-xl border border-gray-200 p-4 flex flex-col">
              <h2 className="font-semibold text-sm mb-3 flex items-center text-gray-800">
                <Search className="w-4 h-4 mr-2 text-indigo-500" />
                Query Knowledge Base
              </h2>
              
              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={handleSearch}
                  className="w-full bg-gray-50 border border-gray-200 rounded-lg py-2 pl-9 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all"
                  placeholder="Press Enter to search..."
                />
              </div>

              <div className="flex-1 overflow-y-auto">
                {searching ? (
                  <div className="flex items-center justify-center py-8 text-gray-400">
                    <Loader2 className="h-5 w-5 animate-spin" />
                  </div>
                ) : searchResults ? (
                  <div className="space-y-3">
                    {/* Answer */}
                    {searchResults.answer && (
                      <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                        <p className="text-xs font-semibold text-indigo-700 mb-1 flex items-center">
                          <BookOpen className="h-3 w-3 mr-1" />
                          RAG Answer
                          {searchResults.model_used && (
                            <span className="ml-auto text-[10px] font-normal text-indigo-400">{searchResults.model_used}</span>
                          )}
                        </p>
                        <p className="text-xs text-indigo-800 leading-relaxed">{searchResults.answer}</p>
                      </div>
                    )}

                    {/* Evidence confidence (FR9.4) */}
                    {searchResults.evidence_confidence && (
                      <div className={`text-[10px] px-3 py-1.5 rounded-md border ${
                        searchResults.verified 
                          ? "bg-emerald-50 border-emerald-200 text-emerald-700" 
                          : "bg-amber-50 border-amber-200 text-amber-700"
                      }`}>
                        Evidence: <strong>{searchResults.evidence_confidence.overall}</strong>
                        {" • "}{searchResults.evidence_confidence.source_count} sources
                        {" • "}{searchResults.evidence_confidence.citation_count} citations
                        {searchResults.verified && <CheckCircle className="inline h-3 w-3 ml-1" />}
                      </div>
                    )}

                    {/* Chunks */}
                    {searchResults.chunks?.map((chunk: any, i: number) => (
                      <div key={i} className="border border-gray-200 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[10px] font-semibold text-gray-600 truncate">
                            {chunk.document_title || "Document"}
                          </span>
                          <div className="flex items-center space-x-1.5">
                            <span className="text-[9px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                              <Tag className="inline h-2.5 w-2.5 mr-0.5" />{chunk.access_tag}
                            </span>
                            {chunk.page_number && (
                              <span className="text-[9px] text-gray-400">p.{chunk.page_number}</span>
                            )}
                          </div>
                        </div>
                        <p className="text-[11px] text-gray-600 leading-relaxed line-clamp-4">
                          {chunk.chunk_text}
                        </p>
                        <div className="mt-1.5 text-[9px] text-gray-400">
                          Score: {(chunk.similarity_score * 100).toFixed(1)}%
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center text-center py-8 text-gray-400">
                    <Database className="w-8 h-8 mb-2 opacity-30" />
                    <p className="text-xs">Enter a query to search the KB.</p>
                    <p className="text-[10px] mt-1 opacity-60">Results filtered by your ACL tags (FR5.2).</p>
                  </div>
                )}
              </div>
            </div>

            {/* Document List */}
            <div className="lg:col-span-2 rounded-xl border border-gray-200 overflow-hidden flex flex-col">
              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between bg-gray-50">
                <h2 className="font-semibold text-sm text-gray-800">Indexed Documents</h2>
                <span className="text-[10px] text-gray-400">{documents.length} Total</span>
              </div>
              
              <div className="flex-1 overflow-auto">
                <table className="w-full text-xs text-left">
                  <thead className="text-[10px] uppercase text-gray-400 border-b border-gray-100 bg-gray-50/50">
                    <tr>
                      <th className="px-4 py-2.5 font-medium">Document</th>
                      <th className="px-4 py-2.5 font-medium">Access Tag</th>
                      <th className="px-4 py-2.5 font-medium">Status</th>
                      <th className="px-4 py-2.5 font-medium">Size</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {loading ? (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-gray-400">
                          <Loader2 className="w-5 h-5 animate-spin mx-auto mb-1" />
                          Loading documents...
                        </td>
                      </tr>
                    ) : documents.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-gray-400">
                          No documents uploaded yet. Upload a file to begin indexing.
                        </td>
                      </tr>
                    ) : documents.map((doc) => (
                      <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 font-medium text-gray-700 flex items-center">
                          <FileText className="w-3.5 h-3.5 mr-2 text-gray-400" />
                          {doc.filename}
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-gray-100 text-gray-600 border border-gray-200">
                            <Tag className="w-2.5 h-2.5 mr-0.5" />
                            {doc.access_tag}
                          </span>
                          {doc.access_tag_status === "PENDING_ADMIN_REVIEW" && (
                            <AlertTriangle className="inline h-3 w-3 ml-1 text-amber-500" />
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-[10px] font-medium ${
                            doc.processing_status === 'completed' ? 'text-emerald-600' : 
                            doc.processing_status === 'failed' ? 'text-red-500' :
                            'text-amber-500'
                          }`}>
                            {doc.processing_status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-400">
                          {(doc.file_size_bytes / 1024).toFixed(1)} KB
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
    </div>
  );
}
