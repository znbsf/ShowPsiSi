#pragma once
#include <QSyntaxHighlighter>
#include <QRegularExpression>
// Formatting only: XML stays plain selectable text; no HTML or resource loading.
class XmlHighlighter final : public QSyntaxHighlighter {
public:
    explicit XmlHighlighter(QTextDocument* document): QSyntaxHighlighter(document) {}
protected:
    void highlightBlock(const QString& text) override {
        struct Rule { const char* pattern; const char* color; };
        static const Rule rules[] = {
            {R"(</?[^\s<>/]+|/?>)", "#78acfa"},
            {R"([A-Za-z_][\w:.-]*(?=\s*=))", "#9cdcfe"},
            {R"("[^"\n]*"|'[^'\n]*')", "#d6a089"},
            {R"(&[A-Za-z0-9#]+;)", "#dcdcaa"}
        };
        for (const auto& rule : rules) {
            auto matches = QRegularExpression(QString::fromLatin1(rule.pattern)).globalMatch(text);
            while (matches.hasNext()) { auto match=matches.next(); setFormat(match.capturedStart(),match.capturedLength(),QColor(rule.color)); }
        }
        int start = previousBlockState()==1 ? 0 : text.indexOf("<!--");
        setCurrentBlockState(0);
        while(start >= 0) {
            const int end=text.indexOf("-->",start);
            if(end<0) {setFormat(start,text.size()-start,QColor("#a3b88c"));setCurrentBlockState(1);break;}
            setFormat(start,end+3-start,QColor("#a3b88c"));start=text.indexOf("<!--",end+3);
        }
    }
};
