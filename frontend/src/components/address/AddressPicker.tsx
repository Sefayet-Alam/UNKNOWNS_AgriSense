"use client";

// Cascading Division -> District -> Upazila -> Union picker.
// Divisions/districts/upazilas ship in src/data/bd-geocodes.json; unions are
// fetched from the backend gazetteer (/api/geo/unions/{upazila_code}) — 7.7k
// rows are too heavy to bundle client-side. Every selection carries the real
// CZIS/BBS code (e.g. union 50819427) that the agent later feeds straight
// into CZIS + weather tools. Codes are NEVER free-typed — this is the guard
// against the "HTTP 200 + null" bad-geocode trap. Union is OPTIONAL (some
// upazilas list none); when picked, its centroid pins the farm to exact
// lat/lon for weather — otherwise the upazila centroid is used.

import { useEffect, useState } from "react";
import { Select, type SelectOption } from "@/components/ui/Select";
import geo from "@/data/bd-geocodes.json";
import { apiUnions, type UnionOption } from "@/lib/api";
import type { Address } from "@/lib/types";

interface Upazila {
  name: string;
  code: string;
}
interface District {
  name: string;
  code: string;
  upazilas: Upazila[];
}
interface Division {
  name: string;
  code: string;
  districts: District[];
}

const DIVISIONS = (geo as { divisions: Division[] }).divisions;

export const EMPTY_ADDRESS: Address = {
  division_name: "",
  division_code: "",
  district_name: "",
  district_code: "",
  upazila_name: "",
  upazila_code: "",
  union_name: "",
  union_code: "",
};

interface Props {
  value: Address;
  onChange: (next: Address) => void;
  onBlur?: () => void;
  error?: string;
}

// Map {name, code} geocode rows → Select's {label, value}.
const toOpts = (rows: { name: string; code: string }[]): SelectOption[] =>
  rows.map((r) => ({ label: r.name, value: r.code }));

export function AddressPicker({ value, onChange, onBlur, error }: Props) {
  const division = DIVISIONS.find((d) => d.code === value.division_code);
  const district = division?.districts.find((z) => z.code === value.district_code);

  const [unions, setUnions] = useState<UnionOption[]>([]);
  const [unionsLoading, setUnionsLoading] = useState(false);

  useEffect(() => {
    if (!value.upazila_code) {
      setUnions([]);
      return;
    }
    let cancelled = false;
    setUnionsLoading(true);
    apiUnions(value.upazila_code)
      .then((rows) => {
        if (!cancelled) setUnions(rows);
      })
      .catch(() => {
        if (!cancelled) setUnions([]);
      })
      .finally(() => {
        if (!cancelled) setUnionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [value.upazila_code]);

  const onDivision = (code: string) => {
    const d = DIVISIONS.find((x) => x.code === code);
    // Changing the division invalidates district + upazila + union — reset.
    onChange({
      ...EMPTY_ADDRESS,
      division_name: d?.name ?? "",
      division_code: d?.code ?? "",
    });
  };

  const onDistrict = (code: string) => {
    const z = division?.districts.find((x) => x.code === code);
    onChange({
      division_name: value.division_name,
      division_code: value.division_code,
      district_name: z?.name ?? "",
      district_code: z?.code ?? "",
      upazila_name: "",
      upazila_code: "",
      union_name: "",
      union_code: "",
    });
  };

  const onUpazila = (code: string) => {
    const u = district?.upazilas.find((x) => x.code === code);
    onChange({
      ...value,
      upazila_name: u?.name ?? "",
      upazila_code: u?.code ?? "",
      union_name: "",
      union_code: "",
    });
  };

  const onUnion = (code: string) => {
    const u = unions.find((x) => x.code === code);
    onChange({
      ...value,
      union_name: u?.name ?? "",
      union_code: u?.code ?? "",
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <Select
        label="Division"
        placeholder="Select division"
        value={value.division_code}
        onChange={onDivision}
        onBlur={onBlur}
        options={toOpts(DIVISIONS)}
      />
      <Select
        label="District"
        placeholder={division ? "Select district" : "Select division first"}
        value={value.district_code}
        onChange={onDistrict}
        onBlur={onBlur}
        disabled={!division}
        options={toOpts(division?.districts ?? [])}
      />
      <Select
        label="Upazila"
        placeholder={district ? "Select upazila" : "Select district first"}
        value={value.upazila_code}
        onChange={onUpazila}
        onBlur={onBlur}
        disabled={!district}
        options={toOpts(district?.upazilas ?? [])}
      />
      <Select
        label="Union (optional)"
        placeholder={
          !value.upazila_code
            ? "Select upazila first"
            : unionsLoading
              ? "Loading unions…"
              : unions.length === 0
                ? "No unions listed for this upazila"
                : "Select union"
        }
        value={value.union_code}
        onChange={onUnion}
        onBlur={onBlur}
        disabled={!value.upazila_code || unionsLoading || unions.length === 0}
        options={toOpts(unions)}
      />
      {error && <p className="text-xs text-status-error">{error}</p>}
    </div>
  );
}
