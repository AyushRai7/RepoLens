"use client";

import { useEffect, useState } from "react";
import { Database, ChevronDown, ChevronRight } from "lucide-react";
import { getDbSchema } from "@/lib/api";
import type { DbTable } from "@/lib/types";

function Loader() {
  return (
    <div className="flex items-center justify-center py-16">
      <span className="w-5 h-5 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
    </div>
  );
}

export default function SchemaTab({
  owner,
  name,
}: {
  owner: string;
  name: string;
}) {
  const [tables, setTables] = useState<DbTable[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    getDbSchema(owner, name).then((r) => {
      setTables(r.tables);
      if (r.tables.length > 0) setExpanded(new Set([r.tables[0].table_name]));
      setLoading(false);
    });
  }, []);

  if (loading) return <Loader />;

  if (tables.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Database className="w-8 h-8 text-white/15 mb-3" />
        <p className="text-white/30 text-sm">No database models detected</p>
        <p className="text-white/20 text-xs mt-1">
          Supported: Django ORM, SQLAlchemy, Prisma, TypeORM
        </p>
      </div>
    );
  }

  const toggle = (t: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(t) ? next.delete(t) : next.add(t);
      return next;
    });

  return (
    <div className="space-y-2">
      {tables.map((table) => {
        const isOpen = expanded.has(table.table_name);
        return (
          <div
            key={table.table_name}
            className="rounded-xl border border-white/8 overflow-hidden"
          >
            <button
              onClick={() => toggle(table.table_name)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/3 transition-colors text-left"
            >
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-violet-400" />
                <span className="text-sm font-medium text-white/80">
                  {table.table_name}
                </span>
                <span className="text-[10px] text-white/25">
                  {table.columns.length} columns
                </span>
              </div>
              <div className="flex items-center gap-2">
                {table.source_file && (
                  <span className="text-[10px] text-white/20 font-mono hidden sm:block">
                    {table.source_file.split("/").pop()}
                  </span>
                )}
                {isOpen ? (
                  <ChevronDown className="w-3.5 h-3.5 text-white/30" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-white/30" />
                )}
              </div>
            </button>

            {isOpen && (
              <div className="border-t border-white/8">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-white/3">
                      <th className="text-left px-4 py-2 text-[10px] font-medium text-white/30">
                        Column
                      </th>
                      <th className="text-left px-4 py-2 text-[10px] font-medium text-white/30">
                        Type
                      </th>
                      <th className="text-left px-4 py-2 text-[10px] font-medium text-white/30">
                        Flags
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {table.columns.map((col) => (
                      <tr key={col.name} className="border-t border-white/5">
                        <td className="px-4 py-2 font-mono text-white/70">
                          {col.name}
                        </td>
                        <td className="px-4 py-2 text-white/40">{col.type}</td>
                        <td className="px-4 py-2">
                          <div className="flex gap-1">
                            {col.pk && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/15 text-yellow-400">
                                PK
                              </span>
                            )}
                            {col.fk && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400">
                                FK
                              </span>
                            )}
                            {col.nullable && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/8 text-white/30">
                                null
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}