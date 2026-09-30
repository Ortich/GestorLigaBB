import React from 'react';
import { X, BookOpen } from 'lucide-react';

export default function RuleModal({ isOpen, onClose, title, subtitle, content }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white bg-slate-800 rounded-full"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="p-3 bg-blood-600/20 text-blood-500 rounded-xl">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">{title}</h3>
            {subtitle && <p className="text-sm text-blood-400 font-semibold">{subtitle}</p>}
          </div>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 text-slate-300 text-sm leading-relaxed mb-6">
          {content}
        </div>

        <button
          onClick={onClose}
          className="w-full py-3 bg-blood-600 hover:bg-blood-500 text-white font-bold rounded-xl shadow-lg transition-colors"
        >
          Entendido
        </button>
      </div>
    </div>
  );
}
