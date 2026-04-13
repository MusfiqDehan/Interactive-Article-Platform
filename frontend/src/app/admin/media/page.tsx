"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { normalizeMediaUrl } from "@/lib/media";
import type { MediaFile } from "@/lib/types";
import { Upload, Trash2, Image, Film, Music, File, Copy, Check } from "lucide-react";

export default function AdminMediaPage() {
  const [files, setFiles] = useState<MediaFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const fetchMedia = async () => {
    try {
      const res = await api.get("/media/");
      setFiles(res.data.results || res.data);
    } catch {
      setError("Failed to load media");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMedia();
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError("");

    const formData = new FormData();
    formData.append("image", file);

    try {
      await api.post("/media/upload/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      fetchMedia();
    } catch {
      setError("Failed to upload file");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this file?")) return;
    try {
      await api.delete(`/media/${id}/`);
      fetchMedia();
    } catch {
      setError("Failed to delete file");
    }
  };

  const copyUrl = (id: number, url: string) => {
    navigator.clipboard.writeText(url);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getIcon = (fileType: string) => {
    switch (fileType) {
      case "image":
        return <Image className="w-5 h-5" />;
      case "video":
        return <Film className="w-5 h-5" />;
      case "audio":
        return <Music className="w-5 h-5" />;
      default:
        return <File className="w-5 h-5" />;
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Media Library
        </h1>
        <label
          className={`btn-primary flex items-center gap-2 cursor-pointer ${
            uploading ? "opacity-50 pointer-events-none" : ""
          }`}
        >
          <Upload className="w-4 h-4" />
          {uploading ? "Uploading..." : "Upload File"}
          <input
            type="file"
            accept="image/*,video/*,audio/*"
            onChange={handleUpload}
            className="hidden"
            disabled={uploading}
          />
        </label>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {files.length === 0 ? (
        <div className="text-center py-12">
          <Image className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-4" />
          <p className="text-slate-500 dark:text-slate-400">
            No media files yet. Upload your first file!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {files.map((file) => (
            <div key={file.id} className="card overflow-hidden group">
              {/* Preview */}
              <div className="aspect-square bg-slate-100 dark:bg-slate-800 flex items-center justify-center overflow-hidden">
                {file.file_type === "image" ? (
                  <img
                    src={normalizeMediaUrl(file.url || file.file)}
                    alt={file.alt_text || file.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="text-slate-400 dark:text-slate-500">
                    {getIcon(file.file_type)}
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="p-3">
                <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                  {file.title}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-slate-500 dark:text-slate-400 capitalize">
                    {file.file_type}
                  </span>
                  {file.file_size && (
                    <>
                      <span className="text-xs text-slate-300">•</span>
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        {formatSize(file.file_size)}
                      </span>
                    </>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 mt-3">
                  <button
                    onClick={() => copyUrl(file.id, normalizeMediaUrl(file.url || file.file))}
                    className="flex-1 text-xs flex items-center justify-center gap-1 py-1.5 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 rounded-lg transition"
                  >
                    {copiedId === file.id ? (
                      <>
                        <Check className="w-3 h-3 text-green-500" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        Copy URL
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(file.id)}
                    className="p-1.5 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition"
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
