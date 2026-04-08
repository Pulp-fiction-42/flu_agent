"use client";

import React, { createContext, useContext, useState, useEffect } from 'react';

export interface FileInfo {
  filename: string;
  path: string;
  size: number;
}

interface FileContextType {
  files: FileInfo[];
  addFiles: (newFiles: FileInfo[]) => void;
  removeFile: (path: string) => void;
  clearFiles: () => void;
}

const FileContext = createContext<FileContextType>({
  files: [],
  addFiles: () => {},
  removeFile: () => {},
  clearFiles: () => {},
});

export function useFiles() {
  return useContext(FileContext);
}

export function FileContextProvider({ children }: { children: React.ReactNode }) {
  const [files, setFiles] = useState<FileInfo[]>([]);

  // Load from session storage to persist during refresh within the same session
  useEffect(() => {
    const saved = sessionStorage.getItem('bioagent_uploaded_files');
    if (saved) {
      try {
        setFiles(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to parse saved files", e);
      }
    }
  }, []);

  useEffect(() => {
    sessionStorage.setItem('bioagent_uploaded_files', JSON.stringify(files));
  }, [files]);

  const addFiles = (newFiles: FileInfo[]) => {
    setFiles(prev => {
      // Avoid duplicates based on path
      const existingPaths = new Set(prev.map(f => f.path));
      const filteredNew = newFiles.filter(f => !existingPaths.has(f.path));
      return [...prev, ...filteredNew];
    });
  };

  const removeFile = (path: string) => {
    setFiles(prev => prev.filter(f => f.path !== path));
  };

  const clearFiles = () => {
    setFiles([]);
  };

  return (
    <FileContext.Provider value={{ files, addFiles, removeFile, clearFiles }}>
      {children}
    </FileContext.Provider>
  );
}
