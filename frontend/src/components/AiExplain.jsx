import React from "react";

const SECTOR_LABELS_EN = {
  "Хүн ам": "Population",
  "Сургууль": "Schools",
  "Дэд бүтэц": "Infrastructure",
  "Бэлчээрийн мал": "Pasture livestock",
  "Газар тариалан": "Crop farming",
  "ХАА": "Agriculture",
  "Эрчим хүч, суурилгасан хүчин чадал": "Energy and installed capacity",
  "Эрчим хүч үйлдвэрлэл": "Energy production",
  "Эрчим хүч дамжуулалт": "Energy transmission",
  "Эрчим хүч хэрэглээ": "Energy consumption",
  "Цахилгаан, хий, ус": "Electricity, gas, and water",
  "Тээврийн хэрэгслийн тоо": "Number of vehicles",
  "Тээврийн ачаа, зорчигч": "Transport freight and passengers",
  "Тээвэр агуулахын салбар": "Transport and warehousing",
  "Алт, Зэс, Нүүрс, Төмрийн хүдэр": "Gold, copper, coal, and iron ore",
  "Уул уурхай, олборлолт": "Mining and quarrying",
  "Цемент, Шохой, Ган": "Cement, lime, and steel",
  "Боловсруулах үйлдвэрлэл": "Manufacturing",
  "Хог хаягдал": "Waste",
  "Усан хангамж": "Water supply",
  "Барилга": "Construction",
  "Бөөний болон жижиглэн": "Wholesale and retail",
  "Аялал жуулчлал": "Tourism",
  "Зочид буудал": "Hotels",
  "Мэдээлэл холбоо": "Information and communications",
  "Санхүү даатгал": "Finance and insurance",
  "Үл хөдлөх": "Real estate",
  "Шинжлэх ухаан": "Science",
  "Удирдлагын болон дэмжлэг": "Administrative and support services",
  "Төрийн удирдлага": "Public administration",
  "Боловсролын салбар": "Education sector",
  "Эрүүл мэнд": "Health",
  "Урлаг үзвэр": "Arts and entertainment",
  "Бусад үйлчилгээ": "Other services",
  "Гадаадын хөрөнгө оруулалт": "Foreign direct investment",
  "ДНБ": "GDP",
  "Ажил эрхлэлт": "Employment",
  "Засгийн газрын орлого": "Government revenue",
  "Өрхийн орлого": "Household income",
  "Ядуурал": "Poverty",
  "Хүрээлэн байгаа орчин": "Environment",
  "Хөрсний чийгшил": "Soil moisture",
  "Ойн сангийн талбай": "Forest area",
  "Ойн 1 га талбайн нөөц": "Forest stock per hectare",
  "Ойн нийт нөөц": "Total forest stock",
  "Ойн арга хэмжээ": "Forest measures",
  "Ойн сан": "Forest resources",
  "Хүлэмжийн хий": "Greenhouse gas",
  "Цахим хөгжлийн индекс": "Digital development index",
  "Хүнсний аюулгүй байдал": "Food security",
  "Гэмт хэрэг": "Crime",
  "Бизнесийн орчин": "Business environment",
  "Авилга": "Corruption",
  "Ухаант засаглал": "Smart governance",
  "Усны нөөц хэрэглээ": "Water resource use",
};

export default function AiExplain({
  text,
  loading,
  onExplain,
  disabled,
  sectors,
  selectedSectors,
  onToggleSector,
  onSelectAllSectors,
  onClearSectors,
  language = "mn",
}) {
  const isEn = language === "en";
  const defaultErrorText = isEn ? "Failed to generate AI explanation" : "AI тайлбар үүсгэхэд алдаа гарлаа";
  const getSectorLabel = (name) => (isEn ? (SECTOR_LABELS_EN[name] || name) : name);

  return (
    <div className="card">
      <div className="cardTitle">{isEn ? "AI Explanation" : "AI тайлбар"}</div>
      <div className="cardDesc">
        {isEn
          ? "Explains each selected sector using mathematics and Vensim logic."
          : "Сонгосон сектор бүрийг математик болон Vensim логикоор тайлбарлана."}
      </div>

      <div className="chatMeta">
        <div>{isEn ? `Select sectors (${(selectedSectors || []).length}):` : `Сектор сонгох (${(selectedSectors || []).length}):`}</div>
      </div>
      <div className="sectorList">
        {(sectors || []).map((s) => {
          const active = (selectedSectors || []).includes(s);
          return (
            <label key={s} className="sectorItem">
              <input
                type="checkbox"
                checked={active}
                onChange={() => onToggleSector?.(s)}
                disabled={loading}
              />
              <span>{getSectorLabel(s)}</span>
            </label>
          );
        })}
      </div>

      <div className="btnRow">
        <button className="btnGhost" onClick={onSelectAllSectors} disabled={loading}>{isEn ? "All" : "Бүгд"}</button>
        <button className="btnGhost" onClick={onClearSectors} disabled={loading}>{isEn ? "Clear" : "Цэвэрлэх"}</button>
      </div>

      <div className="btnRow">
        <button className="btnPrimary" onClick={onExplain} disabled={disabled || loading}>
          {loading ? (isEn ? "Generating explanation..." : "Тайлбар үүсгэж байна...") : (isEn ? "Generate AI explanation" : "AI тайлбар гаргах")}
        </button>
      </div>

      {!loading && (
        <div className="aiText">
          {text || (isEn ? "No explanation yet." : "Тайлбар хараахан алга байна.")}
        </div>
      )}

      {!loading && text === defaultErrorText && (
        <div className="errorText">{defaultErrorText}</div>
      )}
    </div>
  );
}
