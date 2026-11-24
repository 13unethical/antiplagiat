"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch, ApiError } from "@/lib/api";

interface Student {
  id: string;
  name: string;
  checks_count: number;
}

interface Group {
  id: string;
  name: string;
  students: Student[];
}

export default function GroupsPage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [showAddGroup, setShowAddGroup] = useState(false);
  const [showAddStudent, setShowAddStudent] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [newStudentName, setNewStudentName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchGroups = useCallback(async () => {
    try {
      const data = await apiFetch<Group[]>("/api/v1/groups");
      setGroups(data);
      setSelectedGroupId((prev) => prev ?? (data[0]?.id ?? null));
    } catch {
      setError("Ошибка загрузки групп");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  const selectedGroup = groups.find((g) => g.id === selectedGroupId) ?? null;

  async function addGroup(e: React.FormEvent) {
    e.preventDefault();
    if (!newGroupName.trim()) return;
    try {
      const created = await apiFetch<Group>("/api/v1/groups", {
        method: "POST",
        body: JSON.stringify({ name: newGroupName.trim() }),
      });
      setGroups((prev) => [...prev, created]);
      setSelectedGroupId(created.id);
      setNewGroupName("");
      setShowAddGroup(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка");
    }
  }

  async function deleteGroup(id: string) {
    try {
      await apiFetch(`/api/v1/groups/${id}`, { method: "DELETE" });
      setGroups((prev) => {
        const next = prev.filter((g) => g.id !== id);
        if (selectedGroupId === id) {
          setSelectedGroupId(next[0]?.id ?? null);
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка");
    }
  }

  async function addStudent(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedGroup || !newStudentName.trim()) return;
    try {
      const created = await apiFetch<Student>(
        `/api/v1/groups/${selectedGroup.id}/students`,
        {
          method: "POST",
          body: JSON.stringify({ name: newStudentName.trim() }),
        }
      );
      setGroups((prev) =>
        prev.map((g) =>
          g.id === selectedGroup.id
            ? { ...g, students: [...g.students, created] }
            : g
        )
      );
      setNewStudentName("");
      setShowAddStudent(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка");
    }
  }

  async function removeStudent(studentId: string) {
    if (!selectedGroup) return;
    try {
      await apiFetch(
        `/api/v1/groups/${selectedGroup.id}/students/${studentId}`,
        { method: "DELETE" }
      );
      setGroups((prev) =>
        prev.map((g) =>
          g.id === selectedGroup.id
            ? { ...g, students: g.students.filter((s) => s.id !== studentId) }
            : g
        )
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка");
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Группы и классы</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Студенты привязываются к группам — их можно быстро выбрать при проверке
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded-lg flex items-center justify-between">
          {error}
          <button onClick={() => setError("")} className="ml-3 opacity-50 hover:opacity-100">×</button>
        </div>
      )}

      {loading ? (
        <div className="text-sm text-gray-400">Загрузка...</div>
      ) : (
        <div className="flex gap-5">
          {/* Groups list */}
          <div className="w-56 shrink-0">
            <div className="bg-white border rounded-xl overflow-hidden">
              {groups.map((g) => (
                <div
                  key={g.id}
                  onClick={() => setSelectedGroupId(g.id)}
                  className={`flex items-center justify-between px-4 py-3 cursor-pointer border-b last:border-b-0 transition-colors ${
                    selectedGroupId === g.id
                      ? "bg-blue-50 text-blue-700"
                      : "hover:bg-gray-50 text-gray-700"
                  }`}
                >
                  <div>
                    <p className="font-medium text-sm">{g.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{g.students.length} студентов</p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteGroup(g.id); }}
                    className="text-gray-200 hover:text-red-400 transition-colors text-lg leading-none"
                  >
                    ×
                  </button>
                </div>
              ))}
              {showAddGroup ? (
                <form onSubmit={addGroup} className="p-3 border-t">
                  <input
                    autoFocus
                    className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-2"
                    placeholder="11В"
                    value={newGroupName}
                    onChange={(e) => setNewGroupName(e.target.value)}
                  />
                  <div className="flex gap-1.5">
                    <button type="submit" className="flex-1 bg-blue-600 text-white text-xs py-1 rounded hover:bg-blue-700">OK</button>
                    <button type="button" onClick={() => setShowAddGroup(false)} className="flex-1 border text-xs py-1 rounded text-gray-600 hover:bg-gray-50">Отмена</button>
                  </div>
                </form>
              ) : (
                <button
                  onClick={() => setShowAddGroup(true)}
                  className="w-full px-4 py-2.5 text-sm text-blue-600 hover:bg-blue-50 transition-colors border-t"
                >
                  + Добавить группу
                </button>
              )}
            </div>
          </div>

          {/* Students list */}
          <div className="flex-1">
            {!selectedGroup ? (
              <div className="bg-white border rounded-xl p-10 text-center text-gray-400 text-sm">
                Выберите группу слева
              </div>
            ) : (
              <div className="bg-white border rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-5 py-3 border-b bg-gray-50">
                  <h2 className="font-medium text-sm">
                    {selectedGroup.name} · {selectedGroup.students.length} студентов
                  </h2>
                  <button
                    onClick={() => setShowAddStudent(true)}
                    className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
                  >
                    + Добавить студента
                  </button>
                </div>

                {showAddStudent && (
                  <form onSubmit={addStudent} className="px-5 py-3 border-b flex gap-2 items-end">
                    <div className="flex-1">
                      <label className="block text-xs text-gray-500 mb-1">ФИО студента</label>
                      <input
                        autoFocus
                        required
                        className="w-full border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="Иванов Иван"
                        value={newStudentName}
                        onChange={(e) => setNewStudentName(e.target.value)}
                      />
                    </div>
                    <button type="submit" className="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-blue-700">OK</button>
                    <button type="button" onClick={() => setShowAddStudent(false)} className="border px-3 py-1.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50">Отмена</button>
                  </form>
                )}

                {selectedGroup.students.length === 0 ? (
                  <div className="px-5 py-10 text-center text-gray-400 text-sm">
                    Нет студентов. Нажмите «Добавить студента».
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="border-b">
                      <tr>
                        <th className="text-left px-5 py-2.5 text-xs font-medium text-gray-500">ФИО</th>
                        <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500">Проверок</th>
                        <th className="px-4 py-2.5" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {selectedGroup.students.map((s) => (
                        <tr key={s.id} className="hover:bg-gray-50">
                          <td className="px-5 py-3 font-medium text-gray-900">{s.name}</td>
                          <td className="px-4 py-3 text-gray-500">
                            {s.checks_count > 0 ? s.checks_count : <span className="text-gray-300">—</span>}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => removeStudent(s.id)}
                              className="text-xs text-red-400 hover:underline"
                            >
                              Удалить
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
